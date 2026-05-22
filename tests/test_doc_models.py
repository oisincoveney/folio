from folio.doc_models import (
    AnyDocumentData,
    BankTransactionData,
    InvoiceData,
    PayslipData,
    TaxReceiptData,
)


def test_invoice_data_doc_type_literal():
    data = InvoiceData(amount="10.00", target_currency="EUR")
    assert data.doc_type == "invoice"


def test_bank_transaction_normalises_amount():
    data = BankTransactionData(
        transaction_date="2026-05-01",
        amount="€ 1,234.56",
        currency="EUR",
        counterparty="ACME Corp",
        description="May salary",
        running_balance="5000.00",
    )
    assert data.amount == "1234.56"
    assert data.doc_type == "bank_statement"


def test_tax_receipt_defaults():
    data = TaxReceiptData(
        tax_type="income_tax",
        period="2025",
        amount_paid="3200.00",
        jurisdiction="IE",
    )
    assert data.doc_type == "tax_receipt"
    assert data.jurisdiction == "IE"


def test_payslip_normalises_all_numeric_fields():
    data = PayslipData(
        period="2026-04",
        gross_salary="$4,500",
        income_tax="900.00",
        social_tax="450",
        net_pay="3,150.00",
    )
    assert data.gross_salary == "4500.00"
    assert data.income_tax == "900.00"
    assert data.social_tax == "450.00"
    assert data.net_pay == "3150.00"
    assert data.doc_type == "payslip"


def test_invoice_data_importable_from_parse():
    from folio.parse import InvoiceData as ParseInvoiceData

    assert ParseInvoiceData is InvoiceData


def test_any_document_data_is_union():
    # AnyDocumentData should be a type alias covering all four models
    data: AnyDocumentData = InvoiceData(amount="1.00", target_currency="USD")
    assert data.doc_type == "invoice"
