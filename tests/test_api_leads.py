from app.api import leads as leads_module
from app.schemas.response import LeadSuccessResponse


def test_create_lead_returns_success(client, monkeypatch):
    class FakeProcessor:
        def __init__(self, settings):
            self.settings = settings

        def process(self, payload):
            return type(
                "Result",
                (),
                {
                    "lead_id": "lead_test_001",
                    "saved_to_sheets": True,
                    "crm_synced": False,
                    "crm_record_id": "",
                    "message": "Lead saved to Google Sheets. CRM sync is disabled.",
                },
            )()

    monkeypatch.setattr(leads_module, "LeadProcessor", FakeProcessor)

    payload = {
        "name": "John Smith",
        "email": "john@example.com",
        "phone": "+1 (555) 111-2233",
        "message": "Need a quote",
        "source": "website_form",
        "campaign": "spring_campaign",
        "city": "Austin",
    }

    response = client.post("/api/leads", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["lead_id"] == "lead_test_001"
    assert data["saved_to_sheets"] is True
    assert data["crm_synced"] is False


def test_create_lead_validation_error_when_email_missing(client):
    payload = {
        "name": "John Smith",
        "phone": "+1 (555) 111-2233",
        "source": "website_form",
    }

    response = client.post("/api/leads", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"