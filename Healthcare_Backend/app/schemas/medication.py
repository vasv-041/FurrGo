"""
app/schemas/medication.py

Pydantic schemas for medication management.
"""
from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from enum import Enum


class AdherenceStatus(str, Enum):
    """Allowed adherence statuses."""
    TAKEN = "taken"
    MISSED = "missed"
    SNOOZED = "snoozed"


class MedicationBase(BaseModel):
    """Base medication schema with common fields."""
    name: str
    dosage: Optional[str] = None
    frequency: str
    start_date: date
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Medication name cannot be empty")
        return v.strip()

    @field_validator("frequency")
    @classmethod
    def frequency_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Frequency cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def validate_dates(self) -> "MedicationBase":
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class MedicationCreate(MedicationBase):
    """Schema for creating a medication."""
    pass


class MedicationUpdate(BaseModel):
    """Schema for updating a medication (all fields optional)."""
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Medication name cannot be empty")
        return v.strip() if v else v

    @field_validator("frequency")
    @classmethod
    def frequency_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Frequency cannot be empty")
        return v.strip() if v else v

    @model_validator(mode="after")
    def validate_dates(self) -> "MedicationUpdate":
        if self.end_date is not None and self.start_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class MedicationResponse(BaseModel):
    """Response schema for medication."""
    id: int
    user_id: int
    name: str
    dosage: Optional[str]
    frequency: str
    start_date: date
    end_date: Optional[date]
    is_active: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MedicationScheduleBase(BaseModel):
    """Base medication schedule schema."""
    time_of_day: time
    timezone: str = "UTC"
    is_active: bool = True

    @field_validator("timezone")
    @classmethod
    def timezone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Timezone cannot be empty")
        return v.strip()


class MedicationScheduleCreate(MedicationScheduleBase):
    """Schema for creating a medication schedule."""
    pass


class MedicationScheduleUpdate(BaseModel):
    """Schema for updating a medication schedule."""
    time_of_day: Optional[time] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class MedicationScheduleResponse(BaseModel):
    """Response schema for medication schedule."""
    id: int
    medication_id: int
    time_of_day: time
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdherenceLogCreate(BaseModel):
    """Schema for creating an adherence log."""
    scheduled_time: datetime
    status: str  # Will be validated against allowed values
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"taken", "missed", "snoozed"}
        if v not in allowed:
            raise ValueError(f"Adherence status must be one of: {', '.join(allowed)}")
        return v


class AdherenceLogResponse(BaseModel):
    """Response schema for adherence log."""
    id: int
    medication_id: int
    scheduled_time: datetime
    status: str
    recorded_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class AdherenceSummaryResponse(BaseModel):
    """Response schema for adherence summary."""
    medication_id: int
    total_logs: int
    taken_count: int
    missed_count: int
    snoozed_count: int
    adherence_percentage: float
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class MedicationListResponse(BaseModel):
    """Response for listing medications."""
    medications: List["MedicationResponse"]
    total: int