"""Reflex application state for folio."""

import asyncio
import queue
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import reflex as rx

from folio import parse as parse_mod
from folio import storage as storage_mod
from folio.log_parser import parse_opencode_line, system_log
from folio.models import InvoiceRow, LogEntry
from folio.parse import start_parse_job

UPLOAD_DIR = Path(__file__).parent.parent / ".folio_uploads"

# Keyed by job_id; populated before stream_parse background task reads it.
_active_jobs = {}


def _path_exists(p: str) -> bool:
    return Path(p).exists()


class AppState(rx.State):
    """Application state backing the folio UI."""

    model: str = ""
    models: list[dict] = []
    rows: list[InvoiceRow] = []
    selected_file_key: str = ""
    parsing: bool = False
    saving: bool = False
    completed: int = 0
    total: int = 0
    retry_queue: list[str] = []
    retry_running: bool = False
    dest_dir: str = ""
    staged_files: dict[str, list[str]] = {}

    # --- computed vars ---

    @rx.var
    def selected_row(self) -> InvoiceRow:
        """Return the currently selected row, or an empty row."""
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                return row
        return self.rows[0] if self.rows else InvoiceRow()

    @rx.var
    def selected_logs(self) -> list[LogEntry]:
        """Return logs for the selected row as a flat list."""
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                return row.logs
        return self.rows[0].logs if self.rows else []

    @rx.var
    def status_counts(self) -> dict[str, int]:
        """Return a count of rows per status key."""
        counts: dict[str, int] = {"active": 0, "done": 0, "error": 0, "pending": 0}
        for row in self.rows:
            if row.status in counts:
                counts[row.status] += 1
        return counts

    @rx.var
    def has_rows(self) -> bool:
        """Return True when at least one row exists."""
        return len(self.rows) > 0

    @rx.var
    def progress_pct(self) -> int:
        """Return parse progress as a 0-100 integer percentage."""
        if not self.total:
            return 0
        return min(100, int(self.completed / self.total * 100))

    # --- helpers ---

    def _row_index(self, file_key: str) -> int | None:
        for i, row in enumerate(self.rows):
            if row.file_key == file_key:
                return i
        return None

    def _patch_row(self, idx: int, **kwargs: object) -> None:
        self.rows[idx] = self.rows[idx].model_copy(update=kwargs)

    def _append_log(self, idx: int, entry: LogEntry) -> None:
        self._patch_row(idx, logs=[*self.rows[idx].logs, entry])

    # --- simple event handlers ---

    def load_models(self) -> None:
        """Populate the model list from parse module options."""
        options = parse_mod.get_model_options()
        self.models = [{"id": m["id"], "pdf": bool(m["pdf"])} for m in options]
        if not self.model:
            self.model = parse_mod.get_default_model()

    def pick_folder(self) -> None:
        """Open a macOS folder picker and store the chosen path."""
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", "POSIX path of (choose folder)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            self.dest_dir = result.stdout.strip()

    def select_row(self, file_key: str) -> None:
        """Set the active row by file key."""
        self.selected_file_key = file_key

    def update_model(self, model: str) -> None:
        """Update the active model selection."""
        self.model = model

    def set_selected_company(self, v: str) -> None:
        """Set the company field on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, company=v)

    def set_selected_amount(self, v: str) -> None:
        """Set the amount field on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, amount=v)

    def set_selected_target_currency(self, v: str) -> None:
        """Set the target currency on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, target_currency=v)

    def set_selected_invoice_number(self, v: str) -> None:
        """Set the invoice number on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, invoice_number=v)

    def set_selected_invoice_date(self, v: str) -> None:
        """Set the invoice date on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, invoice_date=v)

    def set_selected_description(self, v: str) -> None:
        """Set the description on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, description=v)

    def set_selected_payment_reference(self, v: str) -> None:
        """Set the payment reference on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, payment_reference=v)

    def set_selected_account_number(self, v: str) -> None:
        """Set the account number on the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is not None:
            self._patch_row(idx, account_number=v)

    def rebuild_reference(self) -> None:
        """Re-synthesize the payment reference for the selected row."""
        idx = self._row_index(self.selected_file_key)
        if idx is None:
            return
        row = self.rows[idx]
        data = parse_mod.InvoiceData(
            amount=row.amount,
            targetCurrency=row.target_currency,
            company=row.company,
            invoiceNumber=row.invoice_number,
            invoiceDate=row.invoice_date,
            description=row.description,
            accountNumber=row.account_number,
            paymentReference=row.payment_reference,
        )
        ref = parse_mod._synthesize_payment_reference(data)  # noqa: SLF001
        self._patch_row(idx, payment_reference=ref)

    def handle_folder_source(self) -> rx.event.EventSpec | None:
        """Open a macOS folder picker and queue all PDFs found within."""
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", "POSIX path of (choose folder)"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        folder = result.stdout.strip()
        pdfs = sorted(Path(folder).rglob("*.pdf"))
        if not pdfs:
            return None
        UPLOAD_DIR.mkdir(exist_ok=True)
        model = self.model or parse_mod.get_default_model()
        temp_files: list[tuple[str, str, str, str]] = []
        for pdf in pdfs:
            name = pdf.name
            source_id = str(uuid.uuid4())
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", dir=UPLOAD_DIR, delete=False,
            ) as tmp:
                tmp.write(pdf.read_bytes())
                tmp_name = tmp.name
            self.staged_files[source_id] = [name, tmp_name]
            self.rows.append(
                InvoiceRow(filename_original=name, file_key=name, source_id=source_id),
            )
            temp_files.append((name, tmp_name, name, source_id))
        if not self.selected_file_key and self.rows:
            self.selected_file_key = self.rows[0].file_key
        q = start_parse_job(temp_files, model)
        job_id = str(uuid.uuid4())
        _active_jobs[job_id] = q
        self.total += len(temp_files)
        self.parsing = True
        return AppState.stream_parse(job_id)  # pyright: ignore[reportReturnType]

    def clear_session(self) -> None:
        """Reset all session state to initial values."""
        self.rows = []
        self.selected_file_key = ""
        self.parsing = False
        self.saving = False
        self.completed = 0
        self.total = 0
        self.retry_queue = []
        self.retry_running = False
        self.staged_files = {}

    # --- event application (mirrors handleEvent in store.js) ---

    def _on_start(self, ev: dict, idx: int) -> None:
        self._patch_row(
            idx,
            status="active",
            parsing=True,
            source_id=ev.get("source_id", self.rows[idx].source_id),
        )
        if not self.selected_file_key:
            self.selected_file_key = ev.get("file_key", "")

    def _on_batch_start(self, ev: dict) -> None:
        target = next(
            (i for i, r in enumerate(self.rows) if r.status == "active"),
            0 if self.rows else None,
        )
        if target is not None:
            n = ev.get("parallelism")
            self._append_log(target, system_log(f"Running up to {n} files in parallel"))

    def _on_attempt(self, ev: dict, idx: int) -> None:
        self._patch_row(idx, status="active", parsing=True)
        msg = f"Attempt {ev.get('attempt')} of {ev.get('max_attempts')}"
        self._append_log(idx, system_log(msg))

    def _on_result(self, ev: dict, idx: int) -> None:
        has_error = bool(ev.get("error"))
        self._patch_row(
            idx,
            amount=ev.get("amount", ""),
            target_currency=ev.get("targetCurrency", "EUR"),
            company=ev.get("company", ""),
            invoice_number=ev.get("invoiceNumber", ""),
            invoice_date=ev.get("invoiceDate", ""),
            description=ev.get("description", ""),
            account_number=ev.get("accountNumber", ""),
            payment_reference=ev.get("paymentReference", ""),
            file_id=ev.get("file_id", "") or "",
            error=ev.get("error", "") or "",
            source_id=ev.get("source_id", self.rows[idx].source_id),
            status="error" if has_error else "done",
            parsing=False,
        )
        self.completed += 1

    def _on_error(self, ev: dict) -> None:
        active_idx = next(
            (i for i, r in enumerate(self.rows) if r.status == "active"),
            self._row_index(self.selected_file_key),
        )
        if active_idx is not None:
            err_msg = ev.get("error", "Stream error")
            self._append_log(
                active_idx,
                LogEntry(
                    stream="system",
                    raw=err_msg,
                    expanded=True,
                    type="system",
                    title="system",
                    body=err_msg,
                ),
            )
            self._patch_row(active_idx, status="error", error=err_msg, parsing=False)

    def _apply_event(self, ev: dict) -> None:
        ev_type = ev.get("type")
        file_key = ev.get("file_key", "")
        idx = self._row_index(file_key) if file_key else None

        if ev_type == "start" and idx is not None:
            self._on_start(ev, idx)
        elif ev_type == "batch_start":
            self._on_batch_start(ev)
        elif ev_type == "raw_log" and idx is not None:
            self._append_log(idx, parse_opencode_line(ev))
        elif ev_type == "attempt" and idx is not None:
            self._on_attempt(ev, idx)
        elif ev_type == "retrying" and idx is not None:
            attempt = (ev.get("attempt") or 1) - 1
            self._append_log(
                idx,
                system_log(f"Retrying after attempt {attempt}: {ev.get('error', '')}"),
            )
        elif ev_type == "result" and idx is not None:
            self._on_result(ev, idx)
        elif ev_type == "error":
            self._on_error(ev)

    # --- upload + streaming ---

    async def handle_upload(
        self, files: list[rx.UploadFile],
    ) -> AsyncGenerator[rx.event.EventSpec]:
        """Stage uploaded PDFs and kick off a parse job."""
        if not files:
            return
        UPLOAD_DIR.mkdir(exist_ok=True)
        model = self.model or parse_mod.get_default_model()
        temp_files: list[tuple[str, str, str, str]] = []

        for file in files:
            name = file.name
            if not name:
                continue
            data = await file.read()
            source_id = str(uuid.uuid4())
            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                dir=UPLOAD_DIR,
                delete=False,
            ) as tmp:
                tmp.write(data)
                tmp_name = tmp.name
            self.staged_files[source_id] = [name, tmp_name]
            self.rows.append(
                InvoiceRow(
                    filename_original=name,
                    file_key=name,
                    source_id=source_id,
                    status="pending",
                ),
            )
            temp_files.append((name, tmp_name, name, source_id))

        if not self.selected_file_key and self.rows:
            self.selected_file_key = self.rows[0].file_key

        q = start_parse_job(temp_files, model)
        job_id = str(uuid.uuid4())
        _active_jobs[job_id] = q
        self.total += len(temp_files)
        self.parsing = True
        yield AppState.stream_parse(job_id)  # pyright: ignore[reportReturnType]

    @rx.event(background=True)
    async def stream_parse(self, job_id: str) -> None:
        """Consume parse events from the job queue and apply them to state."""
        q = _active_jobs.get(job_id)
        if q is None:
            return
        while True:
            try:
                event = await asyncio.to_thread(q.get, block=True, timeout=130)
            except queue.Empty:
                async with self:
                    self.parsing = False
                    self.retry_running = False
                break
            async with self:
                self._apply_event(event)
                if event.get("type") == "done":
                    self.parsing = False
                    self.retry_running = False
                    break
        _active_jobs.pop(job_id, None)

    # --- save ---

    def save_row(self, file_key: str) -> None:
        """Copy the parsed PDF to dest_dir and record a CSV row."""
        idx = self._row_index(file_key)
        if idx is None or not self.dest_dir:
            return
        row = self.rows[idx]
        dest_dir = Path(self.dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        csv_path = dest_dir / "payments.csv"
        result = parse_mod.claim_pending(row.file_id)
        if result is None:
            self._patch_row(
                idx, error="Unknown file_id — already saved or session expired",
            )
            return
        try:
            path, is_temp = result
            ref_num = storage_mod.get_next_ref(csv_path)
            filename = storage_mod.build_invoice_filename(
                {
                    "company": row.company,
                    "invoiceNumber": row.invoice_number,
                    "amount": row.amount,
                    "targetCurrency": row.target_currency,
                    "description": row.description,
                    "paymentReference": row.payment_reference,
                },
            )
            dest = dest_dir / filename
            shutil.move(path, dest) if is_temp else shutil.copy2(path, dest)
            self.staged_files.pop(row.source_id, None)
            storage_mod.append_csv_row(
                csv_path,
                row.target_currency,
                row.amount,
                row.payment_reference,
                ref_num,
            )
            self._patch_row(idx, saved_as=filename, status_ok=True)
        except (OSError, ValueError) as e:
            self._patch_row(idx, error=str(e))

    def save_all_done(self) -> None:
        """Save every completed-but-unsaved row, picking a folder first if none set."""
        if not self.dest_dir:
            self.pick_folder()
        if not self.dest_dir:
            return
        for row in list(self.rows):
            if row.status == "done" and not row.status_ok:
                self.save_row(row.file_key)

    # --- retry ---

    def retry_rows(self, file_keys: list[str]) -> rx.event.EventSpec | None:
        """Reset error rows and re-queue them for parsing."""
        retryable = [
            r
            for r in self.rows
            if r.file_key in file_keys and r.source_id and r.status == "error"
        ]
        if not retryable:
            return None
        for row in retryable:
            if row.file_key not in self.retry_queue:
                self.retry_queue.append(row.file_key)
            idx = self._row_index(row.file_key)
            if idx is not None:
                self._patch_row(
                    idx,
                    status="pending",
                    parsing=False,
                    error="",
                    file_id="",
                    saved_as="",
                    status_ok=False,
                )
        self.completed = max(0, self.completed - len(retryable))
        if not self.parsing:
            return AppState.run_retry_queue()  # pyright: ignore[reportCallIssue]
        return None

    def retry_row(self, file_key: str) -> rx.event.EventSpec | None:
        """Retry a single error row."""
        return self.retry_rows([file_key])

    def retry_failed(self) -> rx.event.EventSpec | None:
        """Retry all error rows."""
        return self.retry_rows([r.file_key for r in self.rows])

    async def run_retry_queue(self) -> AsyncGenerator[rx.event.EventSpec]:
        """Dispatch a parse job for all pending rows in the retry queue."""
        if self.retry_running or not self.retry_queue:
            return
        model = self.model or parse_mod.get_default_model()
        retryable = [
            r
            for r in self.rows
            if r.file_key in self.retry_queue and r.source_id and r.status == "pending"
        ]
        self.retry_queue = [
            k for k in self.retry_queue if not any(r.file_key == k for r in retryable)
        ]
        if not retryable:
            return

        temp_files: list[tuple[str, str, str, str]] = []
        for row in retryable:
            staged = self.staged_files.get(row.source_id)
            if not staged or not _path_exists(staged[1]):
                continue
            temp_files.append(
                (
                    row.filename_original or staged[0],
                    staged[1],
                    row.file_key,
                    row.source_id,
                ),
            )

        if not temp_files:
            return

        q = start_parse_job(temp_files, model)
        job_id = str(uuid.uuid4())
        _active_jobs[job_id] = q
        self.retry_running = True
        self.parsing = True
        yield AppState.stream_parse(job_id)  # pyright: ignore[reportReturnType]
