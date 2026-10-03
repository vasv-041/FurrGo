"""
app/models/user.py

User model with medication relationship.
"""
from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """User model with medication relationship."""
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
