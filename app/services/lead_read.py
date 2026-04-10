from datetime import date, datetime, timezone

from app.adapters.crm import build_crm_adapter
from app.adapters.sheets import GoogleSheetsAdapter
from app.config import Settings
from app.exceptions import AppError
from app.schemas.lead_read import (
    BulkDeleteLeadsResponse,
    DeleteLeadResponse,
    LeadListResponse,
    LeadOut,
    ResendCrmResponse,
)
from app.utils.normalize import normalize_slugish


def _cell(row: list[str], index: int) -> str:
    if index < len(row) and row[index] is not None:
        return str(row[index]).strip()
    return ""


def _row_to_lead_out(row: list[str]) -> LeadOut:
    return LeadOut(
        lead_id=_cell(row, 0),
        created_at=_cell(row, 1),
        name=_cell(row, 2),
        email=_cell(row, 3),
        phone=_cell(row, 4),
        message=_cell(row, 5),
        source=_cell(row, 6),
        campaign=_cell(row, 7),
        city=_cell(row, 8),
        crm_status=_cell(row, 9),
        crm_record_id=_cell(row, 10),
    )


def _parse_created_at(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _day_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _day_end_utc(d: date) -> datetime:
    return datetime(
        d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc
    )


class LeadReadService:
    def __init__(
        self,
        settings: Settings,
        sheets_adapter: GoogleSheetsAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.sheets = sheets_adapter or GoogleSheetsAdapter(settings=settings)

    def _iter_data_rows(self) -> list[list[str]]:
        rows = self.sheets.get_all_rows()
        return rows[1:] if len(rows) > 1 else []

    def list_leads(
        self,
        *,
        source: str | None = None,
        crm_status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> LeadListResponse:
        source_key = normalize_slugish(source) if source else None
        status_key = crm_status.strip().lower() if crm_status else None
        start = _day_start_utc(date_from) if date_from else None
        end = _day_end_utc(date_to) if date_to else None

        items: list[LeadOut] = []
        for row in self._iter_data_rows():
            if not row or not _cell(row, 0):
                continue
            lead = _row_to_lead_out(row)

            if source_key and lead.source != source_key:
                continue
            if status_key and lead.crm_status.strip().lower() != status_key:
                continue
            if start or end:
                created = _parse_created_at(lead.created_at)
                if created is None:
                    continue
                if start and created < start:
                    continue
                if end and created > end:
                    continue

            items.append(lead)

        items.sort(
            key=lambda x: _parse_created_at(x.created_at)
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return LeadListResponse(items=items, total=len(items))

    def get_lead(self, lead_id: str) -> LeadOut:
        for row in self._iter_data_rows():
            if row and _cell(row, 0) == lead_id:
                return _row_to_lead_out(row)
        raise AppError(
            status_code=404,
            error_code="LEAD_NOT_FOUND",
            message=f"Lead '{lead_id}' was not found.",
        )

    def resend_to_crm(self, lead_id: str) -> ResendCrmResponse:
        if not self.settings.enable_crm_sync:
            raise AppError(
                status_code=400,
                error_code="CRM_SYNC_DISABLED",
                message="CRM sync is disabled. Set ENABLE_CRM_SYNC=true to resend leads.",
            )

        sheet_row = self.sheets.find_sheet_row_by_lead_id(lead_id)
        if sheet_row is None:
            raise AppError(
                status_code=404,
                error_code="LEAD_NOT_FOUND",
                message=f"Lead '{lead_id}' was not found.",
            )

        row = self.sheets.get_row_at(sheet_row)
        lead = _row_to_lead_out(row)

        payload = {
            "lead_id": lead.lead_id,
            "created_at": lead.created_at,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "message": lead.message,
            "source": lead.source,
            "campaign": lead.campaign,
            "city": lead.city,
            "crm_status": lead.crm_status,
            "crm_record_id": lead.crm_record_id,
        }

        crm = build_crm_adapter(self.settings)
        crm_result = crm.create_contact_or_deal(payload)

        self.sheets.update_crm_columns(
            sheet_row=sheet_row,
            crm_status=crm_result.status,
            crm_record_id=crm_result.record_id,
        )

        return ResendCrmResponse(
            status="success",
            lead_id=lead_id,
            crm_synced=crm_result.synced,
            crm_record_id=crm_result.record_id,
            crm_status=crm_result.status,
            message="Lead resent to CRM successfully.",
        )

    def delete_lead(self, lead_id: str) -> DeleteLeadResponse:
        sheet_row = self.sheets.find_sheet_row_by_lead_id(lead_id)
        if sheet_row is None:
            raise AppError(
                status_code=404,
                error_code="LEAD_NOT_FOUND",
                message=f"Lead '{lead_id}' was not found.",
            )
        self.sheets.delete_sheet_rows([sheet_row])
        return DeleteLeadResponse(
            status="success",
            lead_id=lead_id,
            message="Lead deleted from the sheet.",
        )

    def delete_leads_bulk(self, lead_ids: list[str]) -> BulkDeleteLeadsResponse:
        unique_ids = list(dict.fromkeys(lead_ids))
        rows: set[int] = set()
        for lid in unique_ids:
            r = self.sheets.find_sheet_row_by_lead_id(lid)
            if r is not None:
                rows.add(r)
        if not rows:
            raise AppError(
                status_code=404,
                error_code="LEAD_NOT_FOUND",
                message="No matching leads were found to delete.",
            )
        self.sheets.delete_sheet_rows(list(rows))
        n = len(rows)
        return BulkDeleteLeadsResponse(
            status="success",
            deleted=n,
            message=f"Deleted {n} lead(s) from the sheet.",
        )
