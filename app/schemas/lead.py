from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    message: str | None = None
    source: str
    campaign: str | None = None
    city: str | None = None
    created_at: datetime | None = None

    @field_validator("name", "source", "phone")
    @classmethod
    def required_text_fields_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Field must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_contain_digits(cls, value: str) -> str:
        digits = [char for char in value if char.isdigit()]
        if len(digits) < 7:
            raise ValueError("Phone must contain at least 7 digits")
        return value