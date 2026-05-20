import parse


def setup_function():
    parse.reset_vendor_normalizer()
    parse.reset_model_cache()


def test_parse_verbose_models_marks_pdf_capability():
    models = parse._parse_verbose_models(
        'anthropic/claude-opus-4-7\n'
        '{\n'
        '  "capabilities": {\n'
        '    "input": {\n'
        '      "pdf": true\n'
        "    }\n"
        "  }\n"
        "}\n"
        "opencode/big-pickle\n"
        "{\n"
        '  "capabilities": {\n'
        '    "input": {\n'
        '      "pdf": false\n'
        "    }\n"
        "  }\n"
        "}\n"
    )

    assert models == [
        {"id": "anthropic/claude-opus-4-7", "pdf": True},
        {"id": "opencode/big-pickle", "pdf": False},
    ]


def test_get_default_model_prefers_opus_4_7(monkeypatch):
    monkeypatch.setattr(
        parse,
        "get_models",
        lambda: ["opencode/big-pickle", "anthropic/claude-opus-4-7"],
    )

    assert parse.get_default_model() == "anthropic/claude-opus-4-7"


def test_try_extract_synthesizes_reference_from_direct_json():
    result = parse._try_extract(
        '{"amount":"2.00","targetCurrency":"USD","company":"US MOBILE INC.",'
        '"invoiceNumber":"830622196","invoiceDate":"2025-12-28",'
        '"description":"1 GB Top Up","accountNumber":"2408"}'
    )

    assert result is not None
    assert result.company == "Us Mobile"
    assert result.paymentReference == "Us Mobile - Inv 830622196 - 1 GB Top Up"


def test_try_extract_synthesizes_reference_from_markdown_fenced_json():
    result = parse._try_extract(
        '```json\n'
        '{"amount":"2.00","targetCurrency":"USD","company":"US MOBILE INC.",'
        '"invoiceNumber":"175234934","invoiceDate":"2025-12-22",'
        '"description":"1 GB Top Up","accountNumber":"2408"}\n'
        '```'
    )

    assert result is not None
    assert result.company == "Us Mobile"
    assert result.paymentReference == "Us Mobile - Inv 175234934 - 1 GB Top Up"


def test_try_extract_accepts_numeric_amount_from_markdown_fenced_json():
    result = parse._try_extract(
        '```json\n'
        '{"amount": 2.00, "targetCurrency": "USD", "company": "US MOBILE INC.",'
        '"invoiceNumber": "404517374", "invoiceDate": "2025-12-24",'
        '"description": "1 GB Top Up", "accountNumber": "2408"}\n'
        '```'
    )

    assert result is not None
    assert result.amount == "2.00"
    assert result.company == "Us Mobile"
    assert result.paymentReference == "Us Mobile - Inv 404517374 - 1 GB Top Up"


def test_try_extract_keeps_company_names_consistent_with_observed_batch_history():
    first = parse._try_extract(
        '{"amount":"2.00","targetCurrency":"usd","company":"US Mobile",'
        '"invoiceNumber":"830622195","description":"1 gb top up"}'
    )
    assert first is not None
    assert first.company == "US Mobile"

    variants = ["US MOBILE INC.", "US Mobile", "us mobile inc", "U.S. Mobile Inc."]

    for company in variants:
        result = parse._try_extract(
            '{"amount":"2.00","targetCurrency":"usd","company":"'
            + company
            + '","invoiceNumber":"830622196","description":"1 gb top up"}'
        )

        assert result is not None
        assert result.company == "US Mobile"
        assert result.targetCurrency == "USD"
        assert result.description == "1 Gb Top Up"
        assert result.paymentReference == "US Mobile - Inv 830622196 - 1 Gb Top Up"
