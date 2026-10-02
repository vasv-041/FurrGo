"""
app/api/routes/health.py

Health-check endpoint — used by load balancers, uptime monitors,
and CI pipelines to confirm the service is running correctly.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Schema for the /health response body."""
    status: str
    service: str

class DatabaseHealthResponse(BaseModel):
    """Schema for the /health/database response body."""
    status: str
    database: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the current health status of the service.",
)
async def health_check() -> HealthResponse:
    """
    GET /health

    Returns a JSON payload indicating the service is healthy.
    This endpoint should always respond with HTTP 200 when the
    application is running correctly.
    """
    return HealthResponse(
        status="healthy",
        service="Healthcare Monitoring Assistant",
    )

@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    summary="Database Health Check",
    description="Returns the connection status to the database.",
)
async def database_health_check(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    """
    GET /health/database
    
    Verifies the connection to the SQLite database.
    """
    try:
        # Simple query to check connection
        db.execute(text("SELECT 1"))
        return DatabaseHealthResponse(
            status="healthy",
            database="connected",
        )
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail="Database connection failed"
        )
