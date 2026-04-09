# Lead Intake API

A FastAPI backend that accepts lead payloads as JSON, validates and normalizes fields, appends a row to Google Sheets, and optionally invokes a CRM adapter (currently **mock only**). Responses are JSON with explicit status and error codes.

---

## Capabilities

| Area | Behavior |
|------|----------|
| **HTTP** | `POST /api/leads` — create a lead; `GET /health` — liveness |
| **Validation** | Required: `name`, `email`, `phone`, `source`. Optional: `message`, `campaign`, `city`, `created_at` |
| **Normalization** | Email, phone, slug-like `source` / `campaign`, UTC datetimes, trimmed text |
| **Google Sheets** | Header row auto-initialization (columns A–K), append one row per lead |
| **CRM** | Optional via `ENABLE_CRM_SYNC`; only a **mock** provider is implemented |
| **Duplicates** | `409` if the sheet already contains the same email or phone (after normalization) |
| **Errors** | Consistent JSON: `status`, `error_code`, `message` |

---

## Current limitations

- No real CRM integration—only a stub to exercise the flow.
- Single request body shape (JSON schema below). There is **no** webhook signing or API-key auth in the app—use a gateway, VPN, or add auth in code for public deployments.
- Deduplication is limited to email and phone against existing sheet rows.

---

## Stack

- Python 3.12+
- FastAPI, Pydantic, Uvicorn
- Google Sheets API (service account)
- Pytest, HTTPX (tests)

---

## Project layout

```text
lead_intake_api/
├── app/
│   ├── api/
│   │   └── leads.py          # POST /api/leads
│   ├── adapters/
│   │   ├── crm.py            # CRM adapters (mock)
│   │   └── sheets.py         # Google Sheets
│   ├── schemas/
│   │   ├── lead.py           # LeadCreate
│   │   └── response.py
│   ├── services/
│   │   └── lead_processor.py # normalize → CRM → Sheets
│   ├── utils/
│   │   ├── ids.py            # lead_id
│   │   ├── logging.py
│   │   └── normalize.py
│   ├── config.py
│   ├── exceptions.py
│   └── main.py               # FastAPI, /health, error handlers
├── credentials/              # service account JSON (not committed)
├── tests/
│   ├── conftest.py
│   ├── test_api_leads.py
│   ├── test_api_errors.py
│   ├── test_lead_processor.py
│   └── test_sheets_adapter.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Local setup

### 1. Virtual environment

```bash
cd lead_intake_api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment

```bash
cp .env.example .env
```

Edit `.env`. The bundled `.env.example` may use `ENABLE_CRM_SYNC=true` for local CRM demo; for **Sheets only**, set:

```env
APP_NAME=Lead Intake API
APP_ENV=dev
APP_HOST=127.0.0.1
APP_PORT=8000

ENABLE_CRM_SYNC=false
CRM_PROVIDER=mock

GOOGLE_SHEET_ID=<your_sheet_id>
GOOGLE_SHEET_NAME=Sheet1
GOOGLE_CREDENTIALS_PATH=credentials/service_account.json
```

---

## Google Sheets

1. Google Cloud project → enable **Google Sheets API**.
2. Create a **service account** and download the JSON key.
3. Place the file under `credentials/` (path must match `GOOGLE_CREDENTIALS_PATH`, default `credentials/service_account.json`).
4. Open the spreadsheet → **Share** → add the service account email from the JSON as **Editor**.

---

## Run the server

From the project root:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- OpenAPI UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

---

## API: request body (`POST /api/leads`)

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `name` | string | yes | |
| `email` | string | yes | Valid email |
| `phone` | string | yes | At least 7 digits |
| `source` | string | yes | e.g. `website_form` |
| `message` | string \| null | no | |
| `campaign` | string \| null | no | |
| `city` | string \| null | no | |
| `created_at` | string (ISO 8601) \| null | no | Defaults to current UTC if omitted |

### Example `curl`

```bash
curl -s -X POST "http://127.0.0.1:8000/api/leads" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "email": "john@example.com",
    "phone": "+1 (555) 111-2233",
    "message": "Need a quote for HVAC installation",
    "source": "website_form",
    "campaign": "google_ads_spring",
    "city": "Austin, TX",
    "created_at": "2026-04-09T09:15:00Z"
  }'
```

### Success response (200)

`lead_id` format: `lead_<YYYYMMDDHHMMSS>_<6_hex>` (example: `lead_20260409121530_a1b2c3`).

```json
{
  "status": "success",
  "lead_id": "lead_20260409121530_a1b2c3",
  "saved_to_sheets": true,
  "crm_synced": false,
  "crm_record_id": "",
  "message": "Lead processed successfully"
}
```

The HTTP `message` field is always `"Lead processed successfully"` in the current implementation, regardless of CRM being enabled (the processor may compute different internal messages for future use).

---

## CRM mode (mock)

In `.env`:

```env
ENABLE_CRM_SYNC=true
CRM_PROVIDER=mock
```

Restart the server. Expected:

- Row is still written to Google Sheets.
- Sheet columns `crm_status` (e.g. `created`) and `crm_record_id` are filled.
- JSON response: `crm_synced: true`, non-empty `crm_record_id`.

With `ENABLE_CRM_SYNC=true`, any `CRM_PROVIDER` other than `mock` returns `CRM_PROVIDER_NOT_SUPPORTED` (see `app/adapters/crm.py`).

---

## Common errors

**Validation (422)** — first Pydantic error, wrapped as:

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "..."
}
```

**Duplicate (409)**

```json
{
  "status": "error",
  "error_code": "DUPLICATE_LEAD",
  "message": "Lead with this email already exists."
}
```

(or the phone variant.)

**Google Sheets** — e.g. bad tab name (`GOOGLE_SHEETS_RANGE_ERROR`), permission denied (`GOOGLE_SHEETS_PERMISSION_DENIED`), not found (`GOOGLE_SHEETS_NOT_FOUND`). Check `error_code` in the response body.

---

## Tests

```bash
pytest
pytest -v
pytest tests/test_api_leads.py -v
pytest tests/test_lead_processor.py -v
```

Coverage includes: happy-path API, validation errors, processor (including CRM and duplicates), and parts of Sheets / app error handling.

---

## Possible next steps

- Real CRM adapter for a chosen provider.
- Authenticate inbound requests (API key or webhook signature).
- Docker, CI, broader Google API mocks in tests.
