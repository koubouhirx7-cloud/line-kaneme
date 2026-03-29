from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InquiryBase(BaseModel):
    customer_name: str
    phone_number: str
    pickup_location: Optional[str] = None
    delivery_location: Optional[str] = None
    detail: Optional[str] = None

class InquiryCreate(InquiryBase):
    pass

class InquiryResponse(InquiryBase):
    id: str
    status: str
    dispatched_to_partner_id: Optional[int] = None
    reminder_sent: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True

class PartnerBase(BaseModel):
    name: str
    line_group_id: Optional[str] = None
    icon_emoji: str = "🏢"
    is_active: bool = True
    sort_order: int = 0

class PartnerCreate(PartnerBase):
    pass

class PartnerResponse(PartnerBase):
    id: int

    class Config:
        orm_mode = True
        from_attributes = True

class DispatchRequest(BaseModel):
    partner_id: int
