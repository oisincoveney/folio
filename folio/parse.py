"""Invoice PDF parsing via opencode subprocess."""

import dataclasses
import json
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import TextIOWrapper

from pydantic import BaseModel, ValidationError, field_validator

from folio.config import OPENCODE, PARSE_PROMPT
from folio.normalization import (
    ObservedVendorNormalizer,
    clean_text,
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_description,
    normalize_invoice_number,
)

_pending: dict[str, str] = {}
_pending_source: dict[str, str] = {}
_pending_lock = threading.Lock()

PREFERRED_MODEL = "anthropic/claude-opus-4-7"
_MODELS_TTL = 60.0
MAX_PARSE_ATTEMPTS = 2
MAX_PARALLEL_PARSE = max(1, int(os.environ.get("FOLIO_PARSE_PARALLELISM", "3")))

# Mutable containers avoid global reassignment while preserving module-level state.
_models_cache: list[tuple[list[dict[str, str | bool]], float]] = [([], 0.0)]
_vendor_normalizer: list[ObservedVendorNormalizer] = [ObservedVendorNormalizer()]


class InvoiceData(BaseModel):
    """Pydantic model for structured invoice data from opencode JSON output."""

    amount: str
    targetCurrency: str
    company: str = ""
    invoiceNumber: str = ""
    invoiceDate: str = ""
    description: str = ""
    accountNumber: str = ""
    paymentReference: str = ""

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount_field(cls, value: object) -> str:
        """Normalize the amount field before validation."""
        return normalize_amount(value)


@dataclasses.dataclass
class _ParseTask:
    orig_name: str
    pdf_path: str
    file_key: str
    source_id: str
    model: str
    index: int
    total: int
    is_temp: bool


def _clean_reference_part(value: str) -> str:
    return clean_text(value)


def reset_vendor_normalizer() -> None:
    """Reset the session-scoped vendor normalizer (for testing)."""
    _vendor_normalizer[0] = ObservedVendorNormalizer()


def reset_model_cache() -> None:
    """Reset the model list cache (for testing)."""
    _models_cache[0] = ([], 0.0)


def _groom_invoice_data(data: InvoiceData) -> InvoiceData:
    data.company = _vendor_normalizer[0].normalize(data.company)
    data.description = normalize_description(data.description)
    data.invoiceNumber = normalize_invoice_number(data.invoiceNumber)
    data.invoiceDate = normalize_date(data.invoiceDate)
    data.accountNumber = clean_text(data.accountNumber)
    data.targetCurrency = normalize_currency(data.targetCurrency)
    return data


def _dedupe_words(parts: list[str]) -> list[str]:
    result = []
    seen = set()
    for part in parts:
        key = part.casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(part)
    return result


def _synthesize_payment_reference(data: InvoiceData) -> str:
    company = _clean_reference_part(data.company)
    invoice = _clean_reference_part(data.invoiceNumber)
    description = _clean_reference_part(data.description)
    account = _clean_reference_part(data.accountNumber)

    parts = [company]
    if invoice:
        parts.append(f"Inv {invoice}")
    elif account:
        parts.append(account)
    if description and description.casefold() != company.casefold():
        parts.append(description)

    reference = " - ".join(_dedupe_words([part for part in parts if part]))
    if not reference:
        reference = _clean_reference_part(data.paymentReference)
    if not reference:
        reference = company or description or invoice or account
    return reference[:80]


def _parse_verbose_models(output: str) -> list[dict[str, str | bool]]:
    models = []
    lines = output.splitlines()
    i = 0

    while i < len(lines):
        model_id = lines[i].strip()
        i += 1
        if not model_id or "/" not in model_id:
            continue

        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines) or not lines[i].lstrip().startswith("{"):
            models.append({"id": model_id, "pdf": False})
            continue

        block = []
        depth = 0
        while i < len(lines):
            line = lines[i]
            block.append(line)
            depth += line.count("{") - line.count("}")
            i += 1
            if depth == 0:
                break

        try:
            meta = json.loads("\n".join(block))
            pdf = bool(meta.get("capabilities", {}).get("input", {}).get("pdf"))
        except json.JSONDecodeError:
            pdf = False
        models.append({"id": model_id, "pdf": pdf})

    return models


def get_model_options() -> list[dict[str, str | bool]]:
    """Return available opencode models with PDF capability flags, cached for 60s."""
    cached, ts = _models_cache[0]
    if cached and (time.monotonic() - ts) < _MODELS_TTL:
        return cached

    result = subprocess.run(  # noqa: S603
        [OPENCODE, "models", "--verbose"],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    models = _parse_verbose_models(result.stdout)
    if not models:
        result = subprocess.run(  # noqa: S603
            [OPENCODE, "models"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        models = [
            {"id": line.strip(), "pdf": False}
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    _models_cache[0] = (models, time.monotonic())
    return models


def get_models() -> list[str]:
    """Return a flat list of model ID strings."""
    return [str(model["id"]) for model in get_model_options()]


def get_default_model() -> str:
    """Return the preferred model if available, otherwise the first in the list."""
    models = get_models()
    if PREFERRED_MODEL in models:
        return PREFERRED_MODEL
    return models[0] if models else ""


def claim_pending(file_id: str) -> tuple[str, bool] | None:
    """Return (path, is_temp) for a pending file ID, consuming the claim."""
    with _pending_lock:
        if file_id in _pending:
            return (_pending.pop(file_id), True)
        if file_id in _pending_source:
            return (_pending_source.pop(file_id), False)
    return None


def _with_reference(data: InvoiceData) -> InvoiceData:
    data = _groom_invoice_data(data)
    data.paymentReference = _synthesize_payment_reference(data)
    return data


def _try_extract(text: str) -> InvoiceData | None:
    try:
        return _with_reference(InvoiceData.model_validate_json(text))
    except ValidationError:
        pass
    m = re.search(r'\{[^{}]*"amount"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            return _with_reference(InvoiceData.model_validate_json(m.group()))
        except ValidationError:
            pass
    return None


def _extract_result(lines: list[str]) -> InvoiceData:
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "text":
            continue
        text = obj.get("part", {}).get("text", "")
        if text:
            result = _try_extract(text)
            if result:
                return result
    msg = "No parseable JSON found in opencode output"
    raise ValueError(msg)


def _read_pipe(
    pipe: TextIOWrapper,
    stream: str,
    sink: list[str],
    task: _ParseTask,
    q: queue.Queue,
) -> None:
    try:
        for line in iter(pipe.readline, ""):
            text = line.rstrip("\n").removesuffix("\r")
            sink.append(text)
            q.put({
                "type": "raw_log",
                "filename": task.orig_name,
                "file_key": task.file_key,
                "source_id": task.source_id,
                "stream": stream,
                "text": text,
            })
    finally:
        pipe.close()


def _run_attempt(attempt: int, task: _ParseTask, q: queue.Queue) -> InvoiceData:
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    q.put({
        "type": "attempt",
        "filename": task.orig_name,
        "file_key": task.file_key,
        "source_id": task.source_id,
        "attempt": attempt,
        "max_attempts": MAX_PARSE_ATTEMPTS,
    })

    proc = subprocess.Popen(  # noqa: S603
        [OPENCODE, "run", "--format", "json", "--file", task.pdf_path,
         "-m", task.model, PARSE_PROMPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None or proc.stderr is None:
        msg = "Unable to read OpenCode output"
        raise RuntimeError(msg)

    t_out = threading.Thread(
        target=_read_pipe,
        args=(proc.stdout, "stdout", stdout_lines, task, q),
        daemon=True,
    )
    t_err = threading.Thread(
        target=_read_pipe,
        args=(proc.stderr, "stderr", stderr_lines, task, q),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    try:
        returncode = proc.wait(timeout=120)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        msg = "OpenCode timed out after 120 seconds"
        raise TimeoutError(msg) from exc

    t_out.join(timeout=2)
    t_err.join(timeout=2)

    if returncode != 0:
        detail = f"OpenCode exited with code {returncode}"
        if stderr_lines:
            detail += "\n" + "\n".join(stderr_lines[-5:])
        raise RuntimeError(detail)

    return _extract_result([line for line in stdout_lines if line.strip()])


def _emit_result(
    task: _ParseTask,
    parsed: InvoiceData | None,
    error: str,
    q: queue.Queue,
) -> None:
    if parsed is None:
        q.put({
            "type": "result",
            "filename_original": task.orig_name,
            "file_key": task.file_key,
            "source_id": task.source_id,
            "amount": "",
            "targetCurrency": "EUR",
            "company": "",
            "invoiceNumber": "",
            "invoiceDate": "",
            "description": "",
            "accountNumber": "",
            "paymentReference": "",
            "file_id": None,
            "error": error or "No parseable JSON found in opencode output",
            "index": task.index,
            "total": task.total,
        })
        return

    file_id = str(uuid.uuid4())
    with _pending_lock:
        if task.is_temp:
            _pending[file_id] = task.pdf_path
        else:
            _pending_source[file_id] = task.pdf_path
    q.put({
        "type": "result",
        "filename_original": task.orig_name,
        "file_key": task.file_key,
        "source_id": task.source_id,
        **parsed.model_dump(),
        "file_id": file_id,
        "error": None,
        "index": task.index,
        "total": task.total,
    })


def _process_one(task: _ParseTask, q: queue.Queue) -> None:
    q.put({
        "type": "start",
        "filename": task.orig_name,
        "file_key": task.file_key,
        "source_id": task.source_id,
        "index": task.index,
        "total": task.total,
        "model": task.model,
    })

    parsed: InvoiceData | None = None
    last_error = ""
    for attempt in range(1, MAX_PARSE_ATTEMPTS + 1):
        try:
            parsed = _run_attempt(attempt, task, q)
            break
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            if attempt < MAX_PARSE_ATTEMPTS:
                q.put({
                    "type": "retrying",
                    "filename": task.orig_name,
                    "file_key": task.file_key,
                    "source_id": task.source_id,
                    "attempt": attempt + 1,
                    "max_attempts": MAX_PARSE_ATTEMPTS,
                    "error": last_error,
                })

    _emit_result(task, parsed, last_error, q)


def start_parse_job(
    temp_files: list[tuple[str, str, str, str]],
    model: str,
) -> queue.Queue:
    """Start a threaded parse job and return a queue of progress events."""
    q: queue.Queue = queue.Queue()

    def run() -> None:
        total = len(temp_files)
        max_workers = min(MAX_PARALLEL_PARSE, total) if total else 1
        q.put({"type": "batch_start", "total": total, "parallelism": max_workers})
        tasks = [
            _ParseTask(orig_name, tmp_path, file_key, source_id, model, i, total,
                       is_temp=True)
            for i, (orig_name, tmp_path, file_key, source_id) in enumerate(temp_files)
        ]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_one, task, q) for task in tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:  # noqa: BLE001
                    q.put({"type": "job_error", "error": str(e)})
        q.put({"type": "done", "total": total})

    threading.Thread(target=run, daemon=True).start()
    return q
