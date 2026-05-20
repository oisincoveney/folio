import json
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, ValidationError, field_validator

from config import OPENCODE, PARSE_PROMPT
from normalization import (
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

PREFERRED_MODEL = "anthropic/claude-opus-4-7"

_models_cache: tuple[list[dict[str, str | bool]], float] = ([], 0.0)
_MODELS_TTL = 60.0
MAX_PARSE_ATTEMPTS = 2
MAX_PARALLEL_PARSE = max(1, int(os.environ.get("FOLIO_PARSE_PARALLELISM", "3")))
_pending_lock = threading.Lock()
_vendor_normalizer = ObservedVendorNormalizer()


class InvoiceData(BaseModel):
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
    def normalize_amount(cls, value):
        return normalize_amount(value)


def _clean_reference_part(value: str) -> str:
    return clean_text(value)


def reset_vendor_normalizer() -> None:
    global _vendor_normalizer
    _vendor_normalizer = ObservedVendorNormalizer()


def reset_model_cache() -> None:
    global _models_cache
    _models_cache = ([], 0.0)


def _groom_invoice_data(data: InvoiceData) -> InvoiceData:
    data.company = _vendor_normalizer.normalize(data.company)
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
    global _models_cache
    cached, ts = _models_cache
    if cached and (time.monotonic() - ts) < _MODELS_TTL:
        return cached

    result = subprocess.run(
        [OPENCODE, "models", "--verbose"],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    models = _parse_verbose_models(result.stdout)
    if not models:
        result = subprocess.run(
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

    _models_cache = (models, time.monotonic())
    return models


def get_models() -> list[str]:
    return [str(model["id"]) for model in get_model_options()]


def get_default_model() -> str:
    models = get_models()
    if PREFERRED_MODEL in models:
        return PREFERRED_MODEL
    return models[0] if models else ""


def claim_pending(file_id: str) -> tuple[str, bool] | None:
    """Returns (path, is_temp) or None. is_temp → shutil.move; else → shutil.copy2."""
    with _pending_lock:
        if file_id in _pending:
            return (_pending.pop(file_id), True)
        if file_id in _pending_source:
            return (_pending_source.pop(file_id), False)
    return None


def _try_extract(text: str) -> InvoiceData | None:
    def with_reference(data: InvoiceData) -> InvoiceData:
        data = _groom_invoice_data(data)
        data.paymentReference = _synthesize_payment_reference(data)
        return data

    try:
        return with_reference(InvoiceData.model_validate_json(text))
    except ValidationError:
        pass
    m = re.search(r'\{[^{}]*"amount"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            return with_reference(InvoiceData.model_validate_json(m.group()))
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
    raise ValueError("No parseable JSON found in opencode output")


def _process_one(
    orig_name: str,
    pdf_path: str,
    file_key: str,
    source_id: str,
    model: str,
    i: int,
    total: int,
    is_temp: bool,
    q: queue.Queue,
) -> None:
    q.put({
        "type": "start",
        "filename": orig_name,
        "file_key": file_key,
        "source_id": source_id,
        "index": i,
        "total": total,
        "model": model,
    })

    def read_pipe(pipe, stream: str, sink: list[str]) -> None:
        try:
            for line in iter(pipe.readline, ""):
                text = line.rstrip("\n")
                if text.endswith("\r"):
                    text = text[:-1]
                sink.append(text)
                q.put({
                    "type": "raw_log",
                    "filename": orig_name,
                    "file_key": file_key,
                    "source_id": source_id,
                    "stream": stream,
                    "text": text,
                })
        finally:
            pipe.close()

    def run_attempt(attempt: int) -> InvoiceData:
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        q.put({
            "type": "attempt",
            "filename": orig_name,
            "file_key": file_key,
            "source_id": source_id,
            "attempt": attempt,
            "max_attempts": MAX_PARSE_ATTEMPTS,
        })

        proc = subprocess.Popen(
            [OPENCODE, "run", "--format", "json", "--file", pdf_path, "-m", model, PARSE_PROMPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if proc.stdout is None or proc.stderr is None:
            raise RuntimeError("Unable to read OpenCode output")

        stdout_thread = threading.Thread(
            target=read_pipe, args=(proc.stdout, "stdout", stdout_lines), daemon=True
        )
        stderr_thread = threading.Thread(
            target=read_pipe, args=(proc.stderr, "stderr", stderr_lines), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()

        try:
            returncode = proc.wait(timeout=120)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            raise TimeoutError("OpenCode timed out after 120 seconds") from exc

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        if returncode != 0:
            detail = f"OpenCode exited with code {returncode}"
            if stderr_lines:
                detail += "\n" + "\n".join(stderr_lines[-5:])
            raise RuntimeError(detail)

        return _extract_result([line for line in stdout_lines if line.strip()])

    last_error = ""
    for attempt in range(1, MAX_PARSE_ATTEMPTS + 1):
        try:
            parsed = run_attempt(attempt)
            break
        except Exception as e:
            last_error = str(e)
            if attempt >= MAX_PARSE_ATTEMPTS:
                parsed = None
            else:
                q.put({
                    "type": "retrying",
                    "filename": orig_name,
                    "file_key": file_key,
                    "source_id": source_id,
                    "attempt": attempt + 1,
                    "max_attempts": MAX_PARSE_ATTEMPTS,
                    "error": last_error,
                })

    try:
        if parsed is None:
            raise ValueError(last_error or "No parseable JSON found in opencode output")

        file_id = str(uuid.uuid4())
        with _pending_lock:
            if is_temp:
                _pending[file_id] = pdf_path
            else:
                _pending_source[file_id] = pdf_path
        q.put({
            "type": "result",
            "filename_original": orig_name,
            "file_key": file_key,
            "source_id": source_id,
            **parsed.model_dump(),
            "file_id": file_id,
            "error": None,
            "index": i,
            "total": total,
        })
    except Exception as e:
        detail = str(e)
        q.put({
            "type": "result",
            "filename_original": orig_name,
            "file_key": file_key,
            "source_id": source_id,
            "amount": "",
            "targetCurrency": "EUR",
            "company": "",
            "invoiceNumber": "",
            "invoiceDate": "",
            "description": "",
            "accountNumber": "",
            "paymentReference": "",
            "file_id": None,
            "error": detail,
            "index": i,
            "total": total,
        })


def start_parse_job(temp_files: list[tuple[str, str, str, str]], model: str) -> queue.Queue:
    q: queue.Queue = queue.Queue()

    def run() -> None:
        total = len(temp_files)
        max_workers = min(MAX_PARALLEL_PARSE, total) if total else 1
        q.put({
            "type": "batch_start",
            "total": total,
            "parallelism": max_workers,
        })
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _process_one,
                    orig_name,
                    tmp_path,
                    file_key,
                    source_id,
                    model,
                    i,
                    total,
                    True,
                    q,
                )
                for i, (orig_name, tmp_path, file_key, source_id) in enumerate(temp_files)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    q.put({"type": "job_error", "error": str(e)})
        q.put({"type": "done", "total": total})

    threading.Thread(target=run, daemon=True).start()
    return q
