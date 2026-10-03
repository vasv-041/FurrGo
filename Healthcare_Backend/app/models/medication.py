"""
app/models/medication.py

Medication and adherence models for Phase 7A.
"""
from datetime import datetime, time, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Date, Time, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum as PyEnum

from app.models.base import Base


class AdherenceStatus(str, PyEnum):
    """Allowed adherence statuses."""
    TAKEN = "taken"
    MISSED = "missed"
    SNOOZED = "snoozed"


class Medication(Base):
    """Medication model for user medication management."""
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=True)  # e.g., "10mg", "1 tablet"
    frequency: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "daily", "twice_daily", "weekly"
    
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="medications")
    schedules: Mapped[list["MedicationSchedule"]] = relationship(
        "MedicationSchedule", 
        back_populates="medication", 
        cascade="all, delete-orphan"
    )
    adherence_logs: Mapped[list["AdherenceLog"]] = relationship(
        "AdherenceLog", 
        back_populates="medication", 
        cascade="all, delete-orphan"
    )


class MedicationSchedule(Base):
    """Medication schedule for reminder times."""
    __tablename__ = "medication_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medication_id: Mapped[int] = mapped_column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False, index=True)
    
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationship
    medication: Mapped["Medication"] = relationship("Medication", back_populates="schedules")


class AdherenceLog(Base):
    """Adherence log for tracking medication intake."""
    __tablename__ = "adherence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    medication_id: Mapped[int] = mapped_column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False, index=True)
    
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[AdherenceStatus] = mapped_column(SQLEnum(AdherenceStatus), nullable=False)
    
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationship
    medication: Mapped["Medication"] = relationship("Medication", back_populates="adherence_logs")