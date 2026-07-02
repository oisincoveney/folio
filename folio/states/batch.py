"""BatchState — parse / row lifecycle + side-panel editing."""

from __future__ import annotations

import asyncio
import queue
import tempfile
import uuid
from collections.abc import AsyncGenerator, Iterable
from pathlib import Path

import reflex as rx
from botocore.exceptions import ClientError

from folio import aws
from folio.log_parser import parse_opencode_line, system_log
from folio.models import InvoiceRow, LogEntry
from folio.services import ingestion as ingestion_svc
from folio.services import parser as parse_mod
from folio.services.ingestion import IngestionError
from folio.services.parser import start_parse_job
from folio.states.model_selection import ModelSelectionState

UPLOAD_DIR = Path(__file__).parent.parent.parent / ".folio_uploads"

# Keyed by job_id; populated before stream_parse background task reads it.
_active_jobs: dict[str, queue.Queue] = {}
_PARSE_QUEUE_TIMEOUT_SECONDS = 130


def _path_exists(p: str) -> bool:
    return Path(p).exists()


class BatchState(ModelSelectionState):
    """Parse + save state for the index page.

    Subclasses ``ModelSelectionState`` so ``self.model`` resolves to the active
    opencode model id at compute time (handle_upload reads it to dispatch a
    parse job). ``model`` / ``models`` and the model-selection handlers
    (``load_models`` / ``update_model``) live on the parent.
    """

    rows: list[InvoiceRow] = []
    selected_file_key: str = ""
    parsing: bool = False
    saving: bool = False
    completed: int = 0
    total: int = 0
    retry_queue: list[str] = []
    retry_running: bool = False
    staged_files: dict[str, list[str]] = {}
    # Log-panel filter: lives here because it's a view over `rows`, and Reflex
    # doesn't allow cross-state `@rx.var` iteration of `self.rows` from a
    # sibling state.
    show_technical: bool = False

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
    def bucket_name(self) -> str:
        """Return the configured S3 bucket name."""
        return aws.bucket_name()

    @rx.var
    def progress_pct(self) -> int:
        """Return parse progress as a 0-100 integer percentage."""
        if not self.total:
            return 0
        return min(100, int(self.completed / self.total * 100))

    @rx.var
    def visible_logs(self) -> list[LogEntry]:
        """Logs for the selected row, filtered by `show_technical`."""
        row_logs: list[LogEntry] = []
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                row_logs = row.logs
                break
        if not row_logs and self.rows:
            row_logs = self.rows[0].logs
        if self.show_technical:
            return row_logs
        return [e for e in row_logs if not e.technical]

    @rx.var
    def hidden_technical_count(self) -> int:
        """Number of technical entries currently hidden by the filter."""
        row_logs: list[LogEntry] = []
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                row_logs = row.logs
                break
        if not row_logs and self.rows:
            row_logs = self.rows[0].logs
        return sum(1 for e in row_logs if e.technical)

    def toggle_technical(self) -> None:
        """Toggle visibility of technical log entries in the log panel."""
        self.show_technical = not self.show_technical

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

    def select_row(self, file_key: str) -> None:
        """Set the active row by file key."""
        self.selected_file_key = file_key

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
            target_currency=row.target_currency,
            company=row.company,
            invoice_number=row.invoice_number,
            invoice_date=row.invoice_date,
            description=row.description,
            account_number=row.account_number,
            payment_reference=row.payment_reference,
        )
        ref = parse_mod._synthesize_payment_reference(data)  # noqa: SLF001
        self._patch_row(idx, payment_reference=ref)

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

    def _on_classifying(self, idx: int) -> None:
        self._patch_row(idx, status="active", parsing=True)
        self._append_log(idx, system_log("Classifying document type"))

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
            doc_type=ev.get("doc_type", "invoice"),
            raw_data=ev.get("raw_data", {}),
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
        elif ev_type == "classifying" and idx is not None:
            self._on_classifying(idx)
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

    async def _collect_upload_chunks(
        self,
        chunks: rx.UploadChunkIterator,
    ) -> list[tuple[str, bytes]]:
        """Collect streamed upload chunks into ordered byte payloads."""
        uploaded_files: list[tuple[str, bytes]] = []
        current_name = ""
        current_data = bytearray()
        current_has_chunk = False

        async for chunk in chunks:
            name = chunk.filename
            if not name:
                continue
            starts_new_file = name != current_name or (
                chunk.offset == 0 and current_has_chunk
            )
            if starts_new_file:
                if current_name:
                    uploaded_files.append((current_name, bytes(current_data)))
                current_name = name
                current_data = bytearray()
                current_has_chunk = False
            if chunk.offset != len(current_data):
                msg = (
                    f"Unexpected upload chunk offset for {name}: "
                    f"{chunk.offset} != {len(current_data)}"
                )
                raise ValueError(msg)
            current_data.extend(chunk.data)
            current_has_chunk = True
        if current_name:
            uploaded_files.append((current_name, bytes(current_data)))
        return uploaded_files

    def _stage_temp_files(
        self,
        uploaded_files: Iterable[tuple[str, bytes]],
    ) -> list[tuple[str, str, str, str]]:
        """Write uploaded bytes to temp files and return parser task tuples."""
        UPLOAD_DIR.mkdir(exist_ok=True)
        temp_files: list[tuple[str, str, str, str]] = []

        for name, data in uploaded_files:
            if not name:
                continue
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

        return temp_files

    def _start_parse_queue(
        self,
        temp_files: list[tuple[str, str, str, str]],
    ) -> str | None:
        """Start parser workers for staged files and return the active job id."""
        if not temp_files:
            return None
        if not self.selected_file_key and self.rows:
            self.selected_file_key = self.rows[0].file_key

        model = self.model or parse_mod.get_default_model()
        q = start_parse_job(temp_files, model)
        job_id = str(uuid.uuid4())
        _active_jobs[job_id] = q
        self.total += len(temp_files)
        self.parsing = True
        return job_id

    async def _next_parse_event(self, q: queue.Queue) -> dict | None:
        """Read the next parser event, returning None when the queue stalls."""
        try:
            return await asyncio.to_thread(
                q.get,
                block=True,
                timeout=_PARSE_QUEUE_TIMEOUT_SECONDS,
            )
        except queue.Empty:
            return None

    def _finish_parse_queue(self) -> None:
        """Mark any parse queue consumer as stopped."""
        self.parsing = False
        self.retry_running = False

    @rx.event(background=True)
    async def handle_upload(
        self,
        chunks: rx.UploadChunkIterator,
    ) -> None:
        """Stage uploaded PDFs from the upload stream and consume parse events."""
        uploaded_files = await self._collect_upload_chunks(chunks)
        if not uploaded_files:
            return

        async with self:
            temp_files = self._stage_temp_files(uploaded_files)
            job_id = self._start_parse_queue(temp_files)
        if job_id is not None:
            await self._stream_parse_queue(job_id)

    @rx.event(background=True)
    async def stream_parse(self, job_id: str) -> None:
        """Consume parse events from the job queue and apply them to state."""
        await self._stream_parse_queue(job_id)

    async def _stream_parse_queue(self, job_id: str) -> None:
        """Consume parse events from an active queue into state."""
        q = _active_jobs.get(job_id)
        if q is None:
            return
        try:
            while True:
                event = await self._next_parse_event(q)
                async with self:
                    if event is None:
                        self._finish_parse_queue()
                        break
                    self._apply_event(event)
                    if event.get("type") == "done":
                        self._finish_parse_queue()
                        break
        finally:
            _active_jobs.pop(job_id, None)

    # --- save ---

    def save_row(self, file_key: str) -> None:
        """Upload the parsed PDF to S3 and record a CSV row."""
        idx = self._row_index(file_key)
        if idx is None:
            return
        row = self.rows[idx]
        result = parse_mod.claim_pending(row.file_id)
        if result is None:
            self._patch_row(
                idx, error="Unknown file_id — already saved or session expired",
            )
            return
        try:
            path, is_temp = result
            data = Path(path).read_bytes()
            if is_temp:
                Path(path).unlink(missing_ok=True)
        except (OSError, ValueError) as e:
            self._patch_row(idx, error=str(e))
            return
        try:
            saved = ingestion_svc.save_record(row, data)
        except IngestionError as e:
            if e.stage == "db":
                # S3 succeeded → mirror original behavior of popping staged_files.
                # Force status_ok=False so a future caller cannot get a green
                # check after a failed DB upsert.
                self.staged_files.pop(row.source_id, None)
                self._patch_row(
                    idx,
                    error=f"DB write failed: {e}",
                    status_ok=False,
                    db_persisted=False,
                )
            else:
                self._patch_row(idx, error=str(e), status_ok=False, db_persisted=False)
            return
        except ClientError as e:
            # Defensive: ingestion already converts ClientError to
            # IngestionError(stage="s3"); keep this catch in case future
            # changes leak one through.
            self._patch_row(idx, error=str(e), status_ok=False, db_persisted=False)
            return
        self.staged_files.pop(row.source_id, None)
        self._patch_row(
            idx,
            saved_as=saved.key,
            status_ok=True,
            db_persisted=saved.db_persisted,
        )

    def save_all_done(self) -> None:
        """Save every completed-but-unsaved row to S3."""
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
            return BatchState.run_retry_queue()  # pyright: ignore[reportCallIssue]
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
        yield BatchState.stream_parse(job_id)  # pyright: ignore[reportReturnType]
