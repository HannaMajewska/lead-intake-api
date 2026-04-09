import pytest

from app.adapters.crm import CRMCreateResult
from app.adapters.sheets import SheetsAppendResult
from app.config import Settings
from app.exceptions import DuplicateLeadError
from app.schemas.lead import LeadCreate
from app.services.lead_processor import LeadProcessor


class FakeSheetsAdapter:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.appended_rows = []

    def get_all_rows(self):
        return self.rows

    def append_lead_row(self, row):
        self.appended_rows.append(row)
        return SheetsAppendResult(saved=True, row_ref="Sheet1!A2:K2")


class FakeCRMAdapter:
    def create_contact_or_deal(self, lead_payload):
        return CRMCreateResult(
            synced=True,
            record_id="crm_mock_999",
            status="created",
        )


def test_process_lead_success_without_crm():
    settings = Settings(
        enable_crm_sync=False,
        google_sheet_id="test-sheet-id",
        google_sheet_name="Sheet1",
        google_credentials_path="credentials/service_account.json",
    )
    sheets = FakeSheetsAdapter(
        rows=[
            [
                "lead_id",
                "created_at",
                "name",
                "email",
                "phone",
                "message",
                "source",
                "campaign",
                "city",
                "crm_status",
                "crm_record_id",
            ]
        ]
    )

    processor = LeadProcessor(
        settings=settings,
        sheets_adapter=sheets,
        crm_adapter=FakeCRMAdapter(),
    )

    payload = LeadCreate(
        name=" John Smith ",
        email="JOHN@example.com",
        phone="+1 (555) 111-2233",
        message=" Need a quote ",
        source="Website Form",
        campaign=" Spring Launch ",
        city=" Austin ",
    )

    result = processor.process(payload)

    assert result.saved_to_sheets is True
    assert result.crm_synced is False
    assert result.crm_record_id == ""
    assert result.message == "Lead saved to Google Sheets. CRM sync is disabled."
    assert len(sheets.appended_rows) == 1

    appended_row = sheets.appended_rows[0]
    assert appended_row[2] == "John Smith"
    assert appended_row[3] == "john@example.com"
    assert appended_row[4] == "+15551112233"
    assert appended_row[6] == "website_form"
    assert appended_row[7] == "spring_launch"


def test_process_lead_with_crm_enabled():
    settings = Settings(
        enable_crm_sync=True,
        crm_provider="mock",
        google_sheet_id="test-sheet-id",
        google_sheet_name="Sheet1",
        google_credentials_path="credentials/service_account.json",
    )
    sheets = FakeSheetsAdapter(
        rows=[
            [
                "lead_id",
                "created_at",
                "name",
                "email",
                "phone",
                "message",
                "source",
                "campaign",
                "city",
                "crm_status",
                "crm_record_id",
            ]
        ]
    )

    processor = LeadProcessor(
        settings=settings,
        sheets_adapter=sheets,
        crm_adapter=FakeCRMAdapter(),
    )

    payload = LeadCreate(
        name="Emma Stone",
        email="emma@example.com",
        phone="+1 555 444 8899",
        message="Interested in pricing",
        source="landing_page",
        campaign="spring_launch",
        city="Chicago",
    )

    result = processor.process(payload)

    assert result.saved_to_sheets is True
    assert result.crm_synced is True
    assert result.crm_record_id == "crm_mock_999"
    assert result.message == "Lead processed successfully"

    appended_row = sheets.appended_rows[0]
    assert appended_row[9] == "created"
    assert appended_row[10] == "crm_mock_999"


def test_process_lead_duplicate_by_email():
    settings = Settings(
        enable_crm_sync=False,
        google_sheet_id="test-sheet-id",
        google_sheet_name="Sheet1",
        google_credentials_path="credentials/service_account.json",
    )
    sheets = FakeSheetsAdapter(
        rows=[
            [
                "lead_id",
                "created_at",
                "name",
                "email",
                "phone",
                "message",
                "source",
                "campaign",
                "city",
                "crm_status",
                "crm_record_id",
            ],
            [
                "lead_old_001",
                "2026-04-09T10:00:00+00:00",
                "Old Lead",
                "john@example.com",
                "+15551112233",
                "",
                "website_form",
                "",
                "",
                "skipped",
                "",
            ],
        ]
    )

    processor = LeadProcessor(
        settings=settings,
        sheets_adapter=sheets,
        crm_adapter=FakeCRMAdapter(),
    )

    payload = LeadCreate(
        name="John Smith",
        email="john@example.com",
        phone="+1 555 999 0000",
        message="Need a quote",
        source="website_form",
        campaign="spring_launch",
        city="Austin",
    )

    with pytest.raises(DuplicateLeadError) as exc_info:
        processor.process(payload)

    assert exc_info.value.error_code == "DUPLICATE_LEAD"
    assert str(exc_info.value) == "Lead with this email already exists."