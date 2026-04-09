import logging
from dataclasses import dataclass

from app.config import Settings
from app.exceptions import AppError


logger = logging.getLogger(__name__)


@dataclass
class CRMCreateResult:
    synced: bool
    record_id: str
    status: str


class BaseCRMAdapter:
    def create_contact_or_deal(self, lead_payload: dict) -> CRMCreateResult:
        raise NotImplementedError


class MockCRMAdapter(BaseCRMAdapter):
    def create_contact_or_deal(self, lead_payload: dict) -> CRMCreateResult:
        lead_id = lead_payload.get("lead_id", "")

        logger.info(
            "crm_sync_mock_success",
            extra={"lead_id": lead_id},
        )

        return CRMCreateResult(
            synced=True,
            record_id=f"crm_mock_{lead_id[-6:]}" if lead_id else "crm_mock_001",
            status="created",
        )


def build_crm_adapter(settings: Settings) -> BaseCRMAdapter:
    if not settings.enable_crm_sync:
        return MockCRMAdapter()

    if settings.crm_provider == "mock":
        return MockCRMAdapter()

    raise AppError(
        status_code=500,
        error_code="CRM_PROVIDER_NOT_SUPPORTED",
        message=f"CRM provider '{settings.crm_provider}' is not supported.",
    )