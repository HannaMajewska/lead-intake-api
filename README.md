# Lead Intake API

## About

**Lead Intake** is a small operations hub for teams that capture leads from websites, campaigns, or internal tools and need a **single, transparent place** to land that data without standing up a full CRM or database project on day one.

**Business problems it helps solve**

- **Central intake** — Turn scattered form submissions or partner feeds into **one structured pipeline**: every lead becomes a row with consistent fields (contact, source, campaign, timestamps, CRM sync state).
- **Operational visibility** — Operators can **search, filter, sort, open details, and clean up** rows (including bulk delete) from a browser, instead of editing the spreadsheet by hand or writing one-off scripts.
- **Lightweight truth store** — **Google Sheets** acts as the team’s shared workbook: easy to audit, export, and share, while the API enforces **validation**, **normalization**, and **duplicate rules** (same email or phone cannot create a second row).
- **CRM readiness** — Optional **CRM sync** (currently a **mock** adapter) models how real integration would work: status and record id columns update when sync runs or when a lead is **resent to CRM** after a fix.
- **Integration-friendly surface** — A clear **JSON API** lets forms, landing pages, or middleware **POST leads programmatically** and receive explicit success or error codes—suitable for glue code, Zapier-style automation, or an internal gateway.

**Who it is for**

Small and mid-sized teams, agencies, or product squads that want **reliable lead capture + a simple console**, already live in **Google Workspace**, and may later plug in a real CRM—without rewriting the intake contract.

---

**What it is technically:** A FastAPI backend that accepts lead payloads as JSON, validates and normalizes fields, appends a row to Google Sheets, and optionally invokes a CRM adapter (currently **mock only**). It also serves a **Lead operations** web console at `/` for browsing and managing rows without using `curl`. Responses are JSON with explicit status and error codes.

---

## Capabilities

| Area | Behavior |
|------|----------|
| **HTTP** | `POST /api/leads` — create; `GET /api/leads` — list (filters); `GET /api/leads/{lead_id}` — detail; `DELETE /api/leads/{lead_id}` — remove sheet row; `POST /api/leads/bulk-delete` — JSON `{ "lead_ids": [...] }` removes matching rows; `POST /api/leads/{lead_id}/resend-crm` — refresh CRM columns; `GET /health`; `GET /` — web dashboard |
| **Validation** | Required: `name`, `email`, `phone`, `source`. Optional: `message`, `campaign`, `city`, `created_at` |
| **Normalization** | Email, phone, slug-like `source` / `campaign`, UTC datetimes, trimmed text |
| **Google Sheets** | Header row auto-initialization (11 columns A–K), append one row per lead, read/update for dashboard, resend, and **row deletion** (single or bulk) |
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
│   │   └── leads.py          # REST: create, list, detail, delete, bulk-delete, resend-crm
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

The dashboard is a single-page console for operators. It reads and filters data through `GET /api/leads`, creates leads with `POST /api/leads`, opens a row with `GET /api/leads/{lead_id}`, deletes rows with `DELETE /api/leads/{lead_id}` or `POST /api/leads/bulk-delete`, and can **Resend to CRM** via `POST /api/leads/{lead_id}/resend-crm` (requires `ENABLE_CRM_SYNC=true`).

### Screenshots

Figures in the subsections below illustrate layout, header, new-lead flow, filters, the table, lead detail, and notifications.

---

### Overall layout

- **Full page** — header, **Find leads** filters, **Leads** table (row selection and bulk delete), and (when open) the **New lead** dialog or lead detail dialog.

<img width="1900" height="959" alt="Screenshot 2026-04-12 at 01 19 54" src="https://github.com/user-attachments/assets/441a24fa-c904-4331-b08b-2042afef5b12" />


---

### Header (top bar)

- **Title** — “Lead operations” and the tagline (sheet-backed intake, CRM, team console).
- **+ Add lead** — opens the **New lead** dialog (modal).
- **API docs** — opens FastAPI Swagger (`/docs`) in a new tab.

<img width="1900" height="132" alt="Screenshot 2026-04-12 at 01 12 08" src="https://github.com/user-attachments/assets/2b7767cc-6323-4588-85a3-b65698d6c89e" />



---

### New lead form

- Opens in a modal dialog when you click **+ Add lead**; **Cancel**, **×**, or Escape closes without saving; a successful **Submit lead** resets the form and closes the dialog.
- **Required:** Name, Email, Phone, Source (same rules as the API).
- **Optional:** Campaign, City, Message.
- **Duplicates** — if the email or phone already exists in the sheet, the API returns **409**; the UI shows a toast with the error message (duplicates never get a new row).
- **Submit lead** — `POST /api/leads`; on success, a toast shows the new `lead_id` and the table refreshes.

<img width="1900" height="961" alt="Screenshot 2026-04-12 at 01 13 06" src="https://github.com/user-attachments/assets/301a7472-80cb-4478-9f53-27772d051b4d" />




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

<img width="1900" height="216" alt="Screenshot 2026-04-12 at 01 13 43" src="https://github.com/user-attachments/assets/0df294f3-c57f-4664-8e5a-5357dd94f041" />




---

### Leads table

- **Leads (N)** — count after filters; **Refresh** reloads from the server with the same filter parameters.
- **Selection** — checkbox per row and **Select all visible** in the header. When at least one row is selected, a **bulk bar** appears: **Delete selected** (`POST /api/leads/bulk-delete`) and **Clear selection**.
- **Columns:** checkbox, **Received**, **Name**, **Email**, **Source** (monospace chip), **Status** (badge: synced / pending / error styling), **Action** (**View** opens the detail modal; **Delete** removes that row via `DELETE /api/leads/{lead_id}` after confirmation in the browser).
- **Sortable headers** — click **Received**, **Name**, **Email**, **Source**, or **Status** to sort. The active column shows **up** or **down** arrows; inactive columns show a faint sort hint (Unicode U+2195 in the UI). First click on **Received** keeps **newest first** by default; text columns default to A→Z, then toggle direction on repeated clicks.
- **View** — loads the row from `GET /api/leads/{lead_id}` and opens the detail modal (not only the visible row snapshot).

<img width="1900" height="750" alt="Screenshot 2026-04-12 at 01 19 27" src="https://github.com/user-attachments/assets/f7a9e85b-dae6-4fd7-8801-c0275357563d" />



---

### Lead detail modal

- Full row fields: IDs, timestamps, contact info, source/campaign/city/message, CRM record id, and a **Status** badge.
- **Resend to CRM** — calls `POST /api/leads/{lead_id}/resend-crm`; on success, sheet columns **crm_status** / **crm_record_id** update and the table refreshes. If CRM sync is disabled in `.env`, the API returns **400** (`CRM_SYNC_DISABLED`) and the toast shows the message.
- **Delete lead** — closes the dialog, then asks for browser confirmation and calls `DELETE /api/leads/{lead_id}`; on success the sheet row is removed and the table refreshes.
- **Close** — × button or Escape (native `<dialog>` behavior).

<img width="1900" height="952" alt="Screenshot 2026-04-11 at 01 25 25" src="https://github.com/user-attachments/assets/6f210047-43c1-4e12-a0f2-8ff0f8757417" />



---

### Toasts (notifications)

- Fixed **bottom-right**: one glass **toast host**; the message line uses a slim **type accent** (info / success / error) for saves, resend, single and bulk deletes, validation, duplicates, network failures, CRM disabled, and other API errors.
- Auto-hide after about **five seconds**.

<img width="1900" height="959" alt="Screenshot 2026-04-12 at 01 21 07" src="https://github.com/user-attachments/assets/781c453c-c18a-4f16-b98e-24a482c78e5b" />



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

### Delete one lead

`DELETE /api/leads/{lead_id}` — removes the spreadsheet row for that id.

```json
{
  "status": "success",
  "lead_id": "lead_20260409121530_a1b2c3",
  "message": "Lead deleted from the sheet."
}
```

### Bulk delete

`POST /api/leads/bulk-delete` with JSON body:

```json
{
  "lead_ids": ["lead_20260409121530_a1b2c3", "lead_20260409121600_d4e5f6"]
}
```

Duplicate ids in the list are ignored; each matching row is deleted once. If **no** ids resolve to sheet rows, the API returns **404** with `LEAD_NOT_FOUND`. On success:

```json
{
  "status": "success",
  "deleted": 2,
  "message": "Deleted 2 lead(s) from the sheet."
}
```

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

**Not found (404)** — missing `lead_id` on detail, resend, delete, or bulk-delete when no rows match:

```json
{
  "status": "error",
  "error_code": "LEAD_NOT_FOUND",
  "message": "Lead 'lead_x' was not found."
}
```

(Bulk delete uses the message *No matching leads were found to delete.* when the list matches nothing.)

**CRM resend disabled (400)**

```json
{
  "status": "error",
  "error_code": "CRM_SYNC_DISABLED",
  "message": "CRM sync is disabled. Set ENABLE_CRM_SYNC=true to resend leads."
}
```

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

Coverage includes: happy-path API, validation errors, processor (including CRM and duplicates), dashboard routes (list, detail, resend, delete, bulk-delete), and parts of Sheets / app error handling.

---

## Possible next steps

- Real CRM adapter for a chosen provider.
- Authenticate inbound requests (API key or webhook signature).
- Docker, CI, broader Google API mocks in tests.
