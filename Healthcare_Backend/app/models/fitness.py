"""
app/models/fitness.py

Fitness data model for Phase 8A.
"""
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class FitnessSource(str, PyEnum):
    """Allowed fitness data sources."""
    GOOGLE_FIT = "google_fit"
    FITNESS_TRACKER = "fitness_tracker"
    MANUAL = "manual"


class FitnessData(Base):
    """Fitness data model for storing user fitness observations."""
    __tablename__ = "fitness_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Fitness metrics (nullable because source may provide steps without sleep or vice versa)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in minutes

    # When the fitness data was recorded (e.g., by the fitness tracker)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Date portion for easy date-based queries
    date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)

    # Source of the data
    source: Mapped[FitnessSource] = mapped_column(SQLEnum(FitnessSource), nullable=False)

    # Timestamps
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
    user: Mapped["User"] = relationship("User", back_populates="fitness_data")