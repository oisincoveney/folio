"""Application configuration and constants."""

import shutil

OPENCODE = shutil.which("opencode") or "opencode"

CLASSIFY_PROMPT = (
    "A PDF document is attached. Classify the document type and reply ONLY with "
    'valid JSON and no markdown fences. Schema: {"doc_type": "<type>"} where '
    "<type> is one of: invoice, bank_statement, tax_receipt, payslip."
)

INVOICE_PROMPT = (
    "A PDF invoice is attached. Read the attached PDF and extract structured "
    "payment metadata. Reply ONLY with valid JSON and no markdown fences. "
    "Use empty strings for unknown fields. Do not invent invoice numbers. "
    "For description, prefer the purchased service/product/period over generic "
    "words like invoice or payment. Schema: "
    '{"amount": "<number>", "targetCurrency": "<3-letter ISO code>", '
    '"company": "<vendor/payee name>", "invoiceNumber": "<invoice/order number>", '
    '"invoiceDate": "<YYYY-MM-DD if available>", '
    '"description": "<short service/product/period>", '
    '"accountNumber": "<customer/account/payment id if useful>"}'
)

BANK_STATEMENT_PROMPT = (
    "A PDF bank statement is attached. Extract one transaction's structured data. "
    "Reply ONLY with valid JSON and no markdown fences. Use empty strings for "
    "unknown fields. Schema: "
    '{"transaction_date": "<YYYY-MM-DD>", "amount": "<number>", '
    '"currency": "<3-letter ISO code>", "counterparty": "<name>", '
    '"description": "<short description>", "running_balance": "<number>"}'
)

TAX_RECEIPT_PROMPT = (
    "A PDF tax receipt is attached. Extract structured tax data. "
    "Reply ONLY with valid JSON and no markdown fences. Use empty strings for "
    "unknown fields. Schema: "
    '{"tax_type": "<e.g. income_tax, vat, social_insurance>", '
    '"period": "<YYYY or YYYY-MM>", "amount_paid": "<number>", '
    '"jurisdiction": "<2-letter ISO country code>"}'
)

PAYSLIP_PROMPT = (
    "A PDF payslip is attached. Extract structured payroll data. "
    "Reply ONLY with valid JSON and no markdown fences. Use empty strings for "
    "unknown fields. Schema: "
    '{"period": "<YYYY-MM>", "gross_salary": "<number>", '
    '"income_tax": "<number>", "social_tax": "<number>", "net_pay": "<number>"}'
)

# Keep PARSE_PROMPT as alias so existing callers don't break.
PARSE_PROMPT = INVOICE_PROMPT

DOC_TYPE_PROMPT: dict[str, str] = {
    "invoice": INVOICE_PROMPT,
    "bank_statement": BANK_STATEMENT_PROMPT,
    "tax_receipt": TAX_RECEIPT_PROMPT,
    "payslip": PAYSLIP_PROMPT,
}

CSV_COLUMNS = [
    "recipientId", "name", "recipientEmail", "recipientDetail",
    "sourceCurrency", "targetCurrency", "amountCurrency",
    "amount", "paymentReference", "referenceNumber", "receiverType",
]
STATIC_FIELDS = {
    "recipientId": "",       # your Wise recipient UUID
    "name": "",              # your name as registered on Wise
    "recipientEmail": "",
    "recipientDetail": "Wise account",
    "sourceCurrency": "EUR",
    "amountCurrency": "source",
    "receiverType": "PERSON",
}
