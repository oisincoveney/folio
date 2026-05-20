# folio

Local Flask web app for accounting admin. Drop a PDF invoice/receipt, fill in three fields, hit Save — the file is renamed to a standard format and a row is appended to the Wise bulk payment CSV.

---

## Workflow

1. User navigates to `http://localhost:5000`
2. Drops a PDF onto the drag-and-drop zone
3. Fills in three fields:
   - **Target Currency** (e.g. `GBP`, `USD` — default `EUR`)
   - **Amount** (e.g. `450`)
   - **Payment Reference** (e.g. `Stripe Invoice May`)
4. Clicks **Save**

**What happens on save:**
- PDF is renamed and saved to the selected folder
- A row is appended to `payments.csv` in the same folder

---

## PDF Filename Format

```
YYYY-MM-DD_PaymentReference_Amount_CURRENCY.pdf
```

- Date = today (auto, not user-entered)
- Payment Reference = spaces replaced with underscores
- Currency = uppercase 3-letter code

**Examples:**
```
2026-05-20_Stripe_Invoice_May_450_EUR.pdf
2026-05-15_AWS_82_USD.pdf
```

---

## Wise Payments CSV

**File:** `payments.csv`  
**Location:** user-selected folder at save time

**All columns:**
```
recipientId, name, recipientEmail, recipientDetail, sourceCurrency,
targetCurrency, amountCurrency, amount, paymentReference, referenceNumber, receiverType
```

**Static fields** (configured in `config.py`):
| Field | Value |
|---|---|
| `recipientId` | *(configured in `config.py`)* |
| `name` | *(configured in `config.py`)* |
| `recipientEmail` | *(empty)* |
| `recipientDetail` | `Wise account` |
| `sourceCurrency` | `EUR` |
| `amountCurrency` | `source` |
| `receiverType` | `PERSON` |

**Dynamic fields** (from user input):
| Field | Source |
|---|---|
| `targetCurrency` | user input |
| `amount` | user input |
| `paymentReference` | user input |
| `referenceNumber` | auto-increment (max existing + 1, starts at 1) |

**If CSV doesn't exist:** create it with the header row, then continue.

---

## Tech Stack

- **Backend:** Python 3, Flask
- **Frontend:** Single HTML page embedded in `app.py` (no separate template files)
- **No database** — CSV is the only persistent store

**Install:**
```bash
pip install flask
```

---

## File Structure

```
your-folder/
├── app.py          ← the whole app (backend + embedded HTML)
└── payments.csv    ← created automatically if missing
```

`app.py` uses `__file__` to resolve paths — run it from anywhere and it saves to the right folder.

---

## API

### `GET /`
Serves the single-page UI.

### `GET /next-ref`
Returns `{"referenceNumber": N}` — used to show the next ref number on page load.

### `POST /save`
**Multipart form fields:**
- `file` — the PDF
- `targetCurrency` — string
- `amount` — number
- `paymentReference` — string

**Response (success):**
```json
{ "success": true, "filename": "2026-05-20_Stripe_450_EUR.pdf", "referenceNumber": 3 }
```

**Response (error):**
```json
{ "error": "Amount is required" }
```

---

## Verification

```bash
cd /path/to/your/accounting/folder
python3 app.py
# open http://localhost:5000
# drop a PDF, fill fields, save
# confirm: renamed PDF appears in folder + new row in payments.csv
```

---

## Future

- AI parsing of dropped PDF to pre-fill the fields automatically
