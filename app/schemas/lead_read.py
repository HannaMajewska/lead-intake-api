from pydantic import BaseModel, Field


class LeadOut(BaseModel):
    lead_id: str
    created_at: str
    name: str
    email: str
    phone: str
    message: str
    source: str
    campaign: str
    city: str
    crm_status: str
    crm_record_id: str


class LeadListResponse(BaseModel):
    items: list[LeadOut]
    total: int = Field(description="Number of items after filters")


class ResendCrmResponse(BaseModel):
    status: str
    lead_id: str
    crm_synced: bool
    crm_record_id: str
    crm_status: str
    message: str


class DeleteLeadResponse(BaseModel):
    status: str
    lead_id: str
    message: str


class BulkDeleteLeadsRequest(BaseModel):
    lead_ids: list[str] = Field(min_length=1)


class BulkDeleteLeadsResponse(BaseModel):
    status: str
    deleted: int
    message: str
