from datetime import date

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas.lead import LeadCreate
from app.schemas.lead_read import (
    BulkDeleteLeadsRequest,
    BulkDeleteLeadsResponse,
    DeleteLeadResponse,
    LeadListResponse,
    LeadOut,
    ResendCrmResponse,
)
from app.schemas.response import LeadSuccessResponse
from app.services.lead_processor import LeadProcessor
from app.services.lead_read import LeadReadService

router = APIRouter(prefix="/api/leads", tags=["leads"])


def get_lead_read_service(
    settings: Settings = Depends(get_settings),
) -> LeadReadService:
    return LeadReadService(settings=settings)


@router.get("", response_model=LeadListResponse)
def list_leads(
    source: str | None = Query(None, description="Normalized source slug (same rules as on create)"),
    crm_status: str | None = Query(
        None,
        description="CRM sync status from sheet (e.g. skipped, created, error)",
    ),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    svc: LeadReadService = Depends(get_lead_read_service),
) -> LeadListResponse:
    return svc.list_leads(
        source=source,
        crm_status=crm_status,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=LeadSuccessResponse)
def create_lead(
    payload: LeadCreate,
    settings: Settings = Depends(get_settings),
) -> LeadSuccessResponse:
    processor = LeadProcessor(settings=settings)
    result = processor.process(payload)

    return LeadSuccessResponse(
        status="success",
        lead_id=result.lead_id,
        saved_to_sheets=result.saved_to_sheets,
        crm_synced=result.crm_synced,
        crm_record_id=result.crm_record_id,
        message="Lead processed successfully",
    )


@router.post("/bulk-delete", response_model=BulkDeleteLeadsResponse)
def bulk_delete_leads(
    payload: BulkDeleteLeadsRequest,
    svc: LeadReadService = Depends(get_lead_read_service),
) -> BulkDeleteLeadsResponse:
    return svc.delete_leads_bulk(payload.lead_ids)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: str,
    svc: LeadReadService = Depends(get_lead_read_service),
) -> LeadOut:
    return svc.get_lead(lead_id)


@router.delete("/{lead_id}", response_model=DeleteLeadResponse)
def delete_lead(
    lead_id: str,
    svc: LeadReadService = Depends(get_lead_read_service),
) -> DeleteLeadResponse:
    return svc.delete_lead(lead_id)


@router.post("/{lead_id}/resend-crm", response_model=ResendCrmResponse)
def resend_lead_to_crm(
    lead_id: str,
    svc: LeadReadService = Depends(get_lead_read_service),
) -> ResendCrmResponse:
    return svc.resend_to_crm(lead_id)
