from fastapi.testclient import TestClient

from app.adapters.sheets import GoogleSheetsAdapter
from app.api.leads import get_lead_read_service
from app.config import Settings
from app.main import app
from app.services.lead_read import LeadReadService


def test_dashboard_root_serves_html(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert b"Lead operations" in r.content


def build_settings(**kwargs) -> Settings:
    base = dict(
        google_sheet_id="test-id",
        google_sheet_name="Sheet1",
        google_credentials_path="credentials/service_account.json",
        enable_crm_sync=True,
        crm_provider="mock",
    )
    base.update(kwargs)
    return Settings(**base)


class FakeSheets:
    HEADER = GoogleSheetsAdapter.HEADER

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows
        self.last_update: tuple[int, str, str] | None = None

    def get_all_rows(self) -> list[list[str]]:
        return self.rows

    def find_sheet_row_by_lead_id(self, lead_id: str) -> int | None:
        for sheet_row, row in enumerate(self.rows[1:], start=2):
            if row and row[0] == lead_id:
                return sheet_row
        return None

    def get_row_at(self, sheet_row: int) -> list[str]:
        return list(self.rows[sheet_row - 1])

    def update_crm_columns(
        self,
        *,
        sheet_row: int,
        crm_status: str,
        crm_record_id: str,
    ) -> None:
        self.last_update = (sheet_row, crm_status, crm_record_id)
        row = self.rows[sheet_row - 1]
        while len(row) < 11:
            row.append("")
        row[9] = crm_status
        row[10] = crm_record_id


def sample_rows() -> list[list[str]]:
    return [
        GoogleSheetsAdapter.HEADER,
        [
            "lead_a",
            "2026-04-05T12:00:00+00:00",
            "Alice",
            "a@test.com",
            "+10000000011",
            "hi",
            "web",
            "c1",
            "NYC",
            "skipped",
            "",
        ],
        [
            "lead_b",
            "2026-04-01T08:00:00+00:00",
            "Bob",
            "b@test.com",
            "+10000000022",
            "",
            "ads",
            "",
            "",
            "created",
            "crm_1",
        ],
    ]


def test_list_leads_returns_items(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get("/api/leads")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        ids = {x["lead_id"] for x in data["items"]}
        assert ids == {"lead_a", "lead_b"}
        assert data["items"][0]["lead_id"] == "lead_a"
    finally:
        app.dependency_overrides.clear()


def test_list_leads_filter_by_source(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get("/api/leads", params={"source": "ads"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["lead_id"] == "lead_b"
    finally:
        app.dependency_overrides.clear()


def test_list_leads_filter_by_crm_status(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get("/api/leads", params={"crm_status": "skipped"})
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["lead_id"] == "lead_a"
    finally:
        app.dependency_overrides.clear()


def test_list_leads_filter_by_date(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get(
            "/api/leads",
            params={"date_from": "2026-04-02", "date_to": "2026-04-30"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["lead_id"] == "lead_a"
    finally:
        app.dependency_overrides.clear()


def test_get_lead_detail(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get("/api/leads/lead_b")
        assert r.status_code == 200
        assert r.json()["email"] == "b@test.com"
    finally:
        app.dependency_overrides.clear()


def test_get_lead_not_found(client: TestClient) -> None:
    settings = build_settings()
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.get("/api/leads/missing")
        assert r.status_code == 404
        assert r.json()["error_code"] == "LEAD_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_resend_crm_updates_sheet(client: TestClient) -> None:
    settings = build_settings()
    rows = sample_rows()
    fake = FakeSheets(rows)
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.post("/api/leads/lead_a/resend-crm")
        assert r.status_code == 200
        body = r.json()
        assert body["crm_synced"] is True
        assert body["crm_status"] == "created"
        assert fake.last_update is not None
        assert fake.last_update[0] == 2
    finally:
        app.dependency_overrides.clear()


def test_resend_crm_when_disabled(client: TestClient) -> None:
    settings = build_settings(enable_crm_sync=False)
    fake = FakeSheets(sample_rows())
    app.dependency_overrides[get_lead_read_service] = lambda: LeadReadService(
        settings=settings,
        sheets_adapter=fake,  # type: ignore[arg-type]
    )
    try:
        r = client.post("/api/leads/lead_a/resend-crm")
        assert r.status_code == 400
        assert r.json()["error_code"] == "CRM_SYNC_DISABLED"
    finally:
        app.dependency_overrides.clear()
