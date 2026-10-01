"""
app/models/base.py

SQLAlchemy declarative base.
"""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass
