"""Reflex application state for folio."""

import asyncio
import datetime
import hashlib
import os
import queue
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import boto3
import reflex as rx
from botocore.exceptions import ClientError

from folio import parse as parse_mod
from folio import storage as storage_mod
from folio.db_models import (
    BankTransactionRecord,
    InvoiceRecord,
    PayslipRecord,
    TaxReceiptRecord,
)
from folio.log_parser import parse_opencode_line, system_log
from folio.models import InvoiceRow, LogEntry
from folio.parse import start_parse_job

_RECORD_CLS = {
    "invoice": InvoiceRecord,
    "bank_statement": BankTransactionRecord,
    "tax_receipt": TaxReceiptRecord,
    "payslip": PayslipRecord,
}

UPLOAD_DIR = Path(__file__).parent.parent / ".folio_uploads"

# Keyed by job_id; populated before stream_parse background task reads it.
_active_jobs = {}


def _s3() -> Any:  # noqa: ANN401
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("FOLIO_BUCKET_ENDPOINT"),
        aws_access_key_id=os.environ.get("FOLIO_BUCKET_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("FOLIO_BUCKET_SECRET_KEY"),
        region_name=os.environ.get("FOLIO_BUCKET_REGION", "auto"),
    )


def _path_exists(p: str) -> bool:
    return Path(p).exists()


def _row_to_record_dict(row: InvoiceRow, key: str, content_hash: str) -> dict[str, str]:
    """Build a record dict from an InvoiceRow for DB upsert."""
    base: dict[str, str] = {
        "file_key": key,
        "content_hash": content_hash,
        "saved_at": datetime.datetime.now(tz=datetime.UTC).date().isoformat(),
        "doc_type": row.doc_type,
        "status": "outstanding",
    }
    if row.doc_type == "invoice":
        base.update({
            "amount": row.amount,
            "currency": row.target_currency,
            "company": row.company,
            "invoice_number": row.invoice_number,
            "invoice_date": row.invoice_date,
            "description": row.description,
            "account_number": row.account_number,
            "payment_reference": row.payment_reference,
        })
    else:
        raw = row.raw_data
        for field in (
            "transaction_date", "amount", "currency", "counterparty", "description",
            "running_balance", "tax_type", "period", "amount_paid", "jurisdiction",
            "gross_salary", "income_tax", "social_tax", "net_pay",
        ):
            val = raw.get(field)
            if isinstance(val, str):
                base[field] = val
    return base


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
    staged_files: dict[str, list[str]] = {}

    # --- file browser state ---
    browser_months: list[str] = []
    browser_files: dict[str, list[dict]] = {}
    browser_loading: bool = False
    browser_month: str = ""

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
        return os.environ.get("FOLIO_BUCKET_NAME", "")

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
            bucket = os.environ.get("FOLIO_BUCKET_NAME", "")
            client = _s3()
            filename = storage_mod.build_invoice_filename(
                {
                    "company": row.company,
                    "invoiceNumber": row.invoice_number,
                    "amount": row.amount,
                    "targetCurrency": row.target_currency,
                    "description": row.description,
                },
            )
            key = storage_mod.object_key(row.doc_type, filename)
            client.put_object(Body=data, Bucket=bucket, Key=key)
            self.staged_files.pop(row.source_id, None)
            if row.doc_type == "invoice":
                csv_key = storage_mod.payments_csv_key()
                ref_num = storage_mod.get_next_ref_s3(client, bucket, csv_key)
                storage_mod.append_csv_row_s3(
                    client, bucket, csv_key,
                    row.target_currency, row.amount, row.payment_reference, ref_num,
                )
            content_hash = hashlib.sha256(data).hexdigest()
            record_cls = _RECORD_CLS.get(row.doc_type, InvoiceRecord)
            try:
                record_cls.upsert(_row_to_record_dict(row, key, content_hash))
            except Exception as db_err:  # noqa: BLE001
                self._patch_row(idx, error=f"DB write failed: {db_err}")
                return
            self._patch_row(idx, saved_as=key, status_ok=True)
        except (OSError, ValueError, ClientError) as e:
            self._patch_row(idx, error=str(e))

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

    # --- file browser ---

    def load_file_browser(self) -> None:
        """Populate browser_months and browser_files from S3 bucket listing."""
        bucket = os.environ.get("FOLIO_BUCKET_NAME", "")
        if not bucket:
            return
        self.browser_loading = True
        client = _s3()
        months: dict[str, list[dict]] = {}
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                parts = key.split("/")
                if len(parts) < 2:  # noqa: PLR2004
                    continue
                month = parts[0]
                months.setdefault(month, []).append({
                    "key": key,
                    "size": str(obj.get("Size", 0)),
                    "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
                    "name": parts[-1],
                })
        self.browser_months = sorted(months.keys(), reverse=True)
        self.browser_files = months
        if self.browser_months and not self.browser_month:
            self.browser_month = self.browser_months[0]
        self.browser_loading = False

    def select_browser_month(self, month: str) -> None:
        """Set the active month in the file browser."""
        self.browser_month = month

    def download_file(self, key: str) -> rx.event.EventSpec:
        """Generate a presigned URL for the given S3 key and redirect to it."""
        bucket = os.environ.get("FOLIO_BUCKET_NAME", "")
        url: str = _s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=300,
        )
        return rx.redirect(url)  # pyright: ignore[reportReturnType]
