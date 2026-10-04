"""
app/schemas/fitness.py

Pydantic schemas for fitness data management.
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from enum import Enum


class FitnessSource(str, Enum):
    """Allowed fitness data sources."""
    GOOGLE_FIT = "google_fit"
    FITNESS_TRACKER = "fitness_tracker"
    MANUAL = "manual"


class FitnessDataBase(BaseModel):
    """Base fitness data schema with common fields."""
    user_id: int
    recorded_at: datetime
    steps: Optional[int] = None
    sleep_duration: Optional[int] = None  # in minutes
    source: FitnessSource

    @field_validator("steps")
    @classmethod
    def steps_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Steps cannot be negative")
        return v

    @field_validator("sleep_duration")
    @classmethod
    def sleep_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Sleep duration cannot be negative")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: FitnessSource) -> FitnessSource:
        if v not in FitnessSource:
            raise ValueError(f"Source must be one of: {', '.join([s.value for s in FitnessSource])}")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_metric(self) -> "FitnessDataBase":
        if self.steps is None and self.sleep_duration is None:
            raise ValueError("At least one of steps or sleep_duration must be provided")
        return self


class FitnessDataCreate(FitnessDataBase):
    """Schema for creating a fitness data record."""
    pass


class FitnessDataUpdate(BaseModel):
    """Schema for updating a fitness data record (all fields optional)."""
    steps: Optional[int] = None
    sleep_duration: Optional[int] = None
    recorded_at: Optional[datetime] = None
    source: Optional[FitnessSource] = None

    @field_validator("steps")
    @classmethod
    def steps_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Steps cannot be negative")
        return v

    @field_validator("sleep_duration")
    @classmethod
    def sleep_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Sleep duration cannot be negative")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: Optional[FitnessSource]) -> Optional[FitnessSource]:
        if v is not None and v not in FitnessSource:
            raise ValueError(f"Source must be one of: {', '.join([s.value for s in FitnessSource])}")
        return v


class FitnessDataResponse(BaseModel):
    """Response schema for fitness data."""
    id: int
    user_id: int
    recorded_at: datetime
    date: date
    steps: Optional[int]
    sleep_duration: Optional[int]
    source: FitnessSource
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FitnessDataListResponse(BaseModel):
    """Response for listing fitness data."""
    fitness_data: List["FitnessDataResponse"]
    total: int


class FitnessDailyResponse(BaseModel):
    """Response for daily fitness summary."""
    user_id: int
    date: date
    total_steps: Optional[int]
    total_sleep_duration: Optional[int]
    sources: List[FitnessSource]
    records: List["FitnessDataResponse"]