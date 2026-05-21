"""Text normalization utilities for invoice fields."""

import datetime
import threading
from decimal import Decimal, InvalidOperation

import pycountry
from cleanco import basename
from dateparser import parse as parse_date
from ftfy import fix_text
from price_parser import Price
from rapidfuzz import fuzz, process
from slugify import slugify
from titlecase import titlecase

_ISO_CURRENCY_LEN = 3


def clean_text(value: object) -> str:
    """Strip, unicode-fix, and collapse whitespace from a raw value."""
    return " ".join(fix_text(str(value or "")).split()).strip(" -_.,")


def normalize_amount(value: object) -> str:
    """Return a 2-decimal string for a numeric or currency-prefixed amount."""
    if value is None:
        return ""
    parsed = Price.fromstring(str(value))
    amount = parsed.amount
    if amount is None:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return clean_text(value)
    return f"{amount.quantize(Decimal('0.01')):.2f}"


def normalize_currency(value: object) -> str:
    """Return an ISO-4217 3-letter currency code, or empty string if unrecognised."""
    currency = clean_text(value).upper()
    if len(currency) != _ISO_CURRENCY_LEN:
        return ""
    return currency if pycountry.currencies.get(alpha_3=currency) else ""


def normalize_date(value: object) -> str:
    """Return an ISO-8601 date string, or empty string if unparseable."""
    text = clean_text(value)
    if not text:
        return ""
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    parsed = parse_date(text, settings={"STRICT_PARSING": True})
    return parsed.date().isoformat() if parsed else ""


def _company_basename(value: object) -> str:
    text = clean_text(value)
    previous = None
    while text and text != previous:
        previous = text
        text = clean_text(basename(text))
    return text


def company_key(value: object) -> str:
    """Return a lowercase kebab-case slug for matching company names."""
    text = _company_basename(value)
    return slugify(text, lowercase=True, separator="-")


def normalize_company(value: object) -> str:
    """Return a title-cased company name with legal suffixes stripped."""
    text = _company_basename(value)
    if not text:
        return ""
    return titlecase(text)


def normalize_description(value: object) -> str:
    """Return a title-cased description string."""
    text = clean_text(value)
    return titlecase(text) if text else ""


def normalize_invoice_number(value: object) -> str:
    """Return an invoice number with internal whitespace removed."""
    return "".join(clean_text(value).split())


class ObservedVendorNormalizer:
    """Normalise company names consistently within a session."""

    def __init__(self, cutoff: int = 90) -> None:
        """Initialise with a fuzzy-match similarity cutoff (0-100)."""
        self.cutoff = cutoff
        self._display_by_key: dict[str, str] = {}
        self._lock = threading.Lock()

    def normalize(self, value: object) -> str:
        """Return the canonical display name for a company, reusing prior matches."""
        key = company_key(value)
        if not key:
            return ""
        display = normalize_company(value)
        with self._lock:
            if key in self._display_by_key:
                return self._display_by_key[key]

            match = process.extractOne(
                key,
                self._display_by_key.keys(),
                scorer=fuzz.WRatio,
                score_cutoff=self.cutoff,
            )
            if match:
                return self._display_by_key[match[0]]

            self._display_by_key[key] = display
            return display
