import shutil

OPENCODE = shutil.which("opencode") or "opencode"

PARSE_PROMPT = (
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
