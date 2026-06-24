"""
Pydantic schemas: the request/response contracts for the API.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmissionRecordCreate(BaseModel):
    activity_name: str = Field(..., examples=["Diesel"])
    scope: int = Field(..., ge=1, le=2, description="1 (direct) or 2 (indirect)")
    section: Optional[str] = Field(None, examples=["Power Plant"])
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., examples=["KL"])
    activity_date: date = Field(..., examples=["2024-06-15"])


class EmissionRecordOut(BaseModel):
    id: int
    activity_name: str
    scope: int
    section: Optional[str]
    quantity: float
    unit: str
    activity_date: date
    calculated_emissions: float
    factor_id_used: Optional[int]
    is_overridden: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OverrideRequest(BaseModel):
    new_value: float = Field(..., ge=0, description="Corrected emissions in kgCO2e")
    reason: str = Field(..., min_length=1, examples=["Meter recalibration; engine value too high"])


class AuditLogOut(BaseModel):
    id: int
    record_id: int
    field_changed: str
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    changed_at: datetime

    class Config:
        from_attributes = True

class BusinessMetricCreate(BaseModel):
    metric_name: str = Field(..., examples=["Tonnes of Steel Produced"])
    value: float = Field(..., ge=0)
    metric_date: date = Field(..., examples=["2024-06-28"])


class BusinessMetricOut(BaseModel):
    id: int
    metric_name: str
    value: float
    metric_date: date

    class Config:
        from_attributes = True