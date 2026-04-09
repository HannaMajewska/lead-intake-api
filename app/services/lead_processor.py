import logging
from dataclasses import dataclass

from app.adapters.crm import CRMCreateResult, BaseCRMAdapter, build_crm_adapter
from app.adapters.sheets import GoogleSheetsAdapter
from app.config import Settings
from app.exceptions import DuplicateLeadError
from app.schemas.lead import LeadCreate
from app.utils.ids import generate_lead_id
from app.utils.normalize import (
    clean_text,
    normalize_created_at,
    normalize_email,
    normalize_phone,
    normalize_slugish,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessedLeadResult:
    lead_id: str
    saved_to_sheets: bool
    crm_synced: bool
    crm_record_id: str
    message: str


class LeadProcessor:
    def __init__(
        self,
        settings: Settings,
        sheets_adapter: GoogleSheetsAdapter | None = None,
        crm_adapter: BaseCRMAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.sheets_adapter = sheets_adapter or GoogleSheetsAdapter(settings=settings)
        self.crm_adapter = crm_adapter or build_crm_adapter(settings=settings)

    def process(self, payload: LeadCreate) -> ProcessedLeadResult:
        logger.info("lead_received")

        lead_id = generate_lead_id()
        normalized_created_at = normalize_created_at(payload.created_at)

        normalized = {
            "lead_id": lead_id,
            "created_at": normalized_created_at.isoformat(),
            "name": clean_text(payload.name),
            "email": normalize_email(payload.email),
            "phone": normalize_phone(payload.phone),
            "message": clean_text(payload.message),
            "source": normalize_slugish(payload.source),
            "campaign": normalize_slugish(payload.campaign),
            "city": clean_text(payload.city),
            "crm_status": "skipped",
            "crm_record_id": "",
        }

        logger.info(
            "lead_normalized",
            extra={
                "lead_id": lead_id,
                "source": normalized["source"],
            },
        )

        self._check_duplicate(
            email=normalized["email"],
            phone=normalized["phone"],
        )

        crm_result = CRMCreateResult(
            synced=False,
            record_id="",
            status="skipped",
        )

        if self.settings.enable_crm_sync:
            crm_result = self.crm_adapter.create_contact_or_deal(normalized)
            normalized["crm_status"] = crm_result.status
            normalized["crm_record_id"] = crm_result.record_id

        row = [
            normalized["lead_id"],
            normalized["created_at"],
            normalized["name"],
            normalized["email"],
            normalized["phone"],
            normalized["message"],
            normalized["source"],
            normalized["campaign"],
            normalized["city"],
            normalized["crm_status"],
            normalized["crm_record_id"],
        ]

        sheets_result = self.sheets_adapter.append_lead_row(row)

        logger.info(
            "lead_processed",
            extra={
                "lead_id": lead_id,
                "saved_to_sheets": sheets_result.saved,
                "crm_synced": crm_result.synced,
            },
        )

        message = "Lead processed successfully"
        if not self.settings.enable_crm_sync:
            message = "Lead saved to Google Sheets. CRM sync is disabled."

        return ProcessedLeadResult(
            lead_id=lead_id,
            saved_to_sheets=sheets_result.saved,
            crm_synced=crm_result.synced,
            crm_record_id=crm_result.record_id,
            message=message,
        )

    def _check_duplicate(self, *, email: str, phone: str) -> None:
        rows = self.sheets_adapter.get_all_rows()

        if not rows:
            return

        data_rows = rows[1:]

        for row in data_rows:
            existing_email = row[3].strip().lower() if len(row) > 3 and row[3] else ""
            existing_phone = row[4].strip() if len(row) > 4 and row[4] else ""

            if email and existing_email == email:
                logger.info(
                    "duplicate_lead_detected",
                    extra={"match_by": "email", "email": email},
                )
                raise DuplicateLeadError(
                    message="Lead with this email already exists."
                )

            if phone and existing_phone == phone:
                logger.info(
                    "duplicate_lead_detected",
                    extra={"match_by": "phone", "phone": phone},
                )
                raise DuplicateLeadError(
                    message="Lead with this phone already exists."
                )