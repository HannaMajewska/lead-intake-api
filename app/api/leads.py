from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.lead import LeadCreate
from app.schemas.response import LeadSuccessResponse
from app.services.lead_processor import LeadProcessor

router = APIRouter(prefix="/api/leads", tags=["leads"])


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