"""Data models shared across the folio package."""

from pydantic import BaseModel


class LogEntry(BaseModel):
    """Structured log entry produced by parsing an opencode output line."""

    stream: str = ""
    raw: str = ""
    expanded: bool = False
    technical: bool = False
    type: str = "raw"
    title: str = ""
    body: str = ""
    meta: str = ""


class InvoiceRow(BaseModel):
    """Invoice data extracted from a single parsed PDF."""

    filename_original: str = ""
    file_key: str = ""
    source_id: str = ""
    status: str = "pending"
    parsing: bool = False
    error: str = ""
    file_id: str = ""
    saved_as: str = ""
    status_ok: bool = False
    logs: list[LogEntry] = []
    amount: str = ""
    target_currency: str = "EUR"
    company: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    description: str = ""
    account_number: str = ""
    payment_reference: str = ""
    doc_type: str = "invoice"
    raw_data: dict = {}
