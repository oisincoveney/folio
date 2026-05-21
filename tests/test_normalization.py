from folio.normalization import (
    ObservedVendorNormalizer,
    normalize_amount,
    normalize_company,
    normalize_currency,
    normalize_date,
    normalize_description,
    normalize_invoice_number,
)


def test_normalizes_invoice_fields_with_libraries():
    assert normalize_amount("USD 1,234.56") == "1234.56"
    assert normalize_currency("usd") == "USD"
    assert normalize_date("Dec 24, 2025") == "2025-12-24"
    assert normalize_company("US MOBILE INC.") == "Us Mobile"
    assert normalize_description("1 gb top up") == "1 Gb Top Up"
    assert normalize_invoice_number(" INV-435367220 ") == "INV-435367220"


def test_rejects_ambiguous_currency_symbols():
    assert normalize_currency("$") == ""
    assert normalize_currency("€") == ""


def test_observed_vendor_normalizer_prefers_consistency_over_acronym_accuracy():
    vendors = ObservedVendorNormalizer()

    assert vendors.normalize("US Mobile") == "US Mobile"
    assert vendors.normalize("US MOBILE INC.") == "US Mobile"
    assert vendors.normalize("us mobile inc") == "US Mobile"


def test_observed_vendor_normalizer_does_not_require_aliases():
    vendors = ObservedVendorNormalizer()

    assert vendors.normalize("Acme Incorporated") == "Acme"
    assert vendors.normalize("ACME INC.") == "Acme"
