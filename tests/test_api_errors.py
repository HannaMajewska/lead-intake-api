from app.api import leads as leads_module
from app.exceptions import AppError


def test_create_lead_returns_app_error_json(client, monkeypatch):
    class FakeProcessor:
        def __init__(self, settings):
            self.settings = settings

        def process(self, payload):
            raise AppError(
                status_code=502,
                error_code="GOOGLE_SHEETS_PERMISSION_DENIED",
                message="Google Sheets access denied. Check sharing permissions for the service account.",
            )

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

    assert response.status_code == 502
    assert response.json() == {
        "status": "error",
        "error_code": "GOOGLE_SHEETS_PERMISSION_DENIED",
        "message": "Google Sheets access denied. Check sharing permissions for the service account.",
    }