from pydantic import BaseModel


class LeadSuccessResponse(BaseModel):
    status: str
    lead_id: str
    saved_to_sheets: bool
    crm_synced: bool
    crm_record_id: str
    message: str


class ErrorResponse(BaseModel):
    status: str
    error_code: str
    message: str