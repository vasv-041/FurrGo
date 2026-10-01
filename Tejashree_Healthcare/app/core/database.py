"""
app/core/database.py

Database setup, engine creation, and session factory.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# If using SQLite, automatically create the directory path
if settings.DATABASE_URL.startswith("sqlite"):
    # Convert 'sqlite:///./data/health_ai.db' to './data/health_ai.db'
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    # In some paths it might be 'sqlite:////absolute/path'
    # But usually it's sqlite:///./path
    if db_path.startswith("./") or db_path.startswith(".\\"):
        dir_name = os.path.dirname(db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

# SQLite requires special connect_args to allow multithreading with FastAPI
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI endpoints to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
