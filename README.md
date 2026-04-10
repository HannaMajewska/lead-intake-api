# Lead Intake API

A FastAPI backend that accepts lead payloads as JSON, validates and normalizes fields, appends a row to Google Sheets, and optionally invokes a CRM adapter (currently **mock only**). It also serves a small **Lead operations** web console at `/` for browsing and managing rows without using `curl`. Responses are JSON with explicit status and error codes.

---

## Capabilities

| Area | Behavior |
|------|----------|
| **HTTP** | `POST /api/leads` — create a lead; `GET /api/leads` — list with optional filters; `GET /api/leads/{lead_id}` — detail; `POST /api/leads/{lead_id}/resend-crm` — push CRM columns again; `GET /health` — liveness; `GET /` — web dashboard |
| **Validation** | Required: `name`, `email`, `phone`, `source`. Optional: `message`, `campaign`, `city`, `created_at` |
| **Normalization** | Email, phone, slug-like `source` / `campaign`, UTC datetimes, trimmed text |
| **Google Sheets** | Header row auto-initialization (columns A–K), append one row per lead, read/update for dashboard and resend |
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
- Static dashboard: HTML, CSS, vanilla JS (`app/static/`)
- Pytest, HTTPX (tests)

---

## Project layout

```text
lead_intake_api/
├── app/
│   ├── api/
│   │   └── leads.py          # REST: create, list, detail, resend-crm
│   ├── adapters/
│   │   ├── crm.py            # CRM adapters (mock)
│   │   └── sheets.py         # Google Sheets read/append/update
│   ├── schemas/
│   │   ├── lead.py           # LeadCreate
│   │   ├── lead_read.py      # list/detail/resend responses
│   │   └── response.py
│   ├── services/
│   │   ├── lead_processor.py # normalize → CRM → Sheets (create)
│   │   └── lead_read.py      # list filters, resend orchestration
│   ├── static/               # dashboard UI (served at /static/, / → index.html)
│   ├── utils/
│   │   ├── ids.py
│   │   ├── logging.py
│   │   └── normalize.py
│   ├── config.py
│   ├── exceptions.py
│   └── main.py               # FastAPI, static mount, /health
├── credentials/              # service account JSON (not committed)
├── tests/
│   ├── conftest.py
│   ├── test_api_leads.py
│   ├── test_api_errors.py
│   ├── test_dashboard_api.py
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

- **Lead operations (dashboard):** `http://127.0.0.1:8000/`
- OpenAPI UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

---

## Web interface: Lead operations

The dashboard is a single-page console for operators. It reads and filters data through `GET /api/leads`, creates leads with `POST /api/leads`, opens a row with `GET /api/leads/{lead_id}`, and can **Resend to CRM** via `POST /api/leads/{lead_id}/resend-crm` (requires `ENABLE_CRM_SYNC=true`).

### Screenshots (optional)

You can keep screenshots next to the repo or in a `docs/screenshots/` folder. Replace the paths in the `![...](...)` lines below with your own files, or delete the image lines if you do not need figures.

Suggested filenames are listed under each subsection so you can capture one screen per topic.

---

### Overall layout

- **Full page** — header, **Find leads** filter card, **Leads** table, and (when open) the **New lead** panel or detail dialog.

<img width="1920" height="952" alt="Screenshot 2026-04-10 at 20 36 19" src="https://github.com/user-attachments/assets/5b7cb66b-6f1f-40e9-a3ff-88ed0e6de23d" />

---

### Header (top bar)

- **Title** — “Lead operations” and the tagline (sheet-backed intake, CRM, team console).
- **+ Add lead** — toggles the **New lead** form panel (hidden until you click).
- **API docs** — opens FastAPI Swagger (`/docs`) in a new tab.

<img width="1920" height="126" alt="Screenshot 2026-04-10 at 20 38 21" src="https://github.com/user-attachments/assets/958a92bf-5f40-420b-a96f-95ee9238b5dd" />


---

### New lead form

- Opens when you click **+ Add lead**; **Cancel** or submit hides it again after a successful create.
- **Required:** Name, Email, Phone, Source (same rules as the API).
- **Optional:** Campaign, City, Message.
- **Duplicates** — if the email or phone already exists in the sheet, the API returns **409**; the UI shows a toast with the error message (duplicates never get a new row).
- **Submit lead** — `POST /api/leads`; on success, a toast shows the new `lead_id` and the table refreshes.

<img width="1902" height="355" alt="Screenshot 2026-04-10 at 20 39 26" src="https://github.com/user-attachments/assets/9ec5cb1a-859d-4510-8fcb-b897348e048b" />


---

### Find leads (filters)

Short help text explains that **filters hit the server** (Google Sheets via the API), while **column sorting** in the table is instant on the rows already loaded in the browser.

- **Source** — search-style field; filters by normalized source slug (same normalization as on create). Updates run automatically after you pause typing (debounced).
- **CRM status** — `All statuses`, **Pending sync (skipped)**, **In CRM (created)**, **Error**. Changing the dropdown refetches immediately.
- **Received (date)** — preset chips:
  - **All time** — no date query parameters.
  - **Last 7 days** / **Last 30 days** — sets `date_from` / `date_to` to a rolling window in the **local** calendar.
  - **Custom range…** — shows **From** and **To** date pickers; edits also refetch.
- **Status line** (under the chips) — shows loading state, then text such as how many leads are shown and the active sort (e.g. “Received: newest first”).
- **Reset filters** — clears source, status, date presets (back to **All time**), and restores default table sort (**Received**, newest first).

<img width="1902" height="306" alt="Screenshot 2026-04-10 at 20 40 03" src="https://github.com/user-attachments/assets/e8b2314e-8c50-4085-956f-78fc09d3c1ae" />


---

### Leads table

- **Leads (N)** — count after filters; **Refresh** reloads from the server with the same filter parameters.
- **Columns:** **Received**, **Name**, **Source** (monospace chip), **Status** (badge: synced / pending / error styling), **View**.
- **Sortable headers** — click **Received**, **Name**, **Source**, or **Status** to sort. The active column shows **up** or **down** arrows; inactive columns show a faint sort hint (Unicode U+2195 in the UI). First click on **Received** keeps **newest first** by default; text columns default to A→Z, then toggle direction on repeated clicks.
- **View** — loads the row from `GET /api/leads/{lead_id}` and opens the detail modal (not only the visible row snapshot).

<img width="1902" height="378" alt="Screenshot 2026-04-10 at 20 40 49" src="https://github.com/user-attachments/assets/32b55736-719d-490d-aba1-d0e25a31e81f" />


---

### Lead detail modal

- Full row fields: IDs, timestamps, contact info, source/campaign/city/message, CRM record id, and a **Status** badge.
- **Resend to CRM** — calls `POST /api/leads/{lead_id}/resend-crm`; on success, sheet columns **crm_status** / **crm_record_id** update and the table refreshes. If CRM sync is disabled in `.env`, the API returns **400** (`CRM_SYNC_DISABLED`) and the toast shows the message.
- **Close** — × button or Escape (native `<dialog>` behavior).

<img width="667" height="549" alt="Screenshot 2026-04-10 at 20 42 07" src="https://github.com/user-attachments/assets/a03cd72c-f5cc-4bc1-8178-bc5eb03678e4" />


---

### Toasts (notifications)

- Bottom-right messages for **success** (e.g. lead saved, resent to CRM), **errors** (validation, duplicate, network, CRM disabled), and general info.
- They auto-hide after a few seconds.

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

### List leads (dashboard and API)

`GET /api/leads` optional query parameters:

| Parameter | Description |
|-----------|-------------|
| `source` | Normalized source slug |
| `crm_status` | Exact sheet value, e.g. `skipped`, `created` |
| `date_from`, `date_to` | ISO calendar dates (`YYYY-MM-DD`), interpreted in UTC day bounds on the server |

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
pytest tests/test_dashboard_api.py -v
```

Coverage includes: happy-path API, validation errors, processor (including CRM and duplicates), dashboard and list/resend routes, and parts of Sheets / app error handling.

---

## Possible next steps

- Real CRM adapter for a chosen provider.
- Authenticate inbound requests (API key or webhook signature).
- Docker, CI, broader Google API mocks in tests.
