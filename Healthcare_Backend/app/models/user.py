"""
app/models/user.py

User model with medication and fitness relationships.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.fitness import FitnessData
    from app.models.medication import Medication


class User(Base):
    """User model with medication and fitness relationships."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Using UTC for standardized timezone-aware timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship to medications
    medications: Mapped[list["Medication"]] = relationship(
        "Medication",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Relationship to fitness data
    fitness_data: Mapped[list["FitnessData"]] = relationship(
        "FitnessData",
        back_populates="user",
        cascade="all, delete-orphan"
    )
