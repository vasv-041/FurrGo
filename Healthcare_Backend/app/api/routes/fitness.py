"""
app/api/routes/fitness.py

Fitness data API routes for Phase 8A.
"""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session

from app.schemas.fitness import (
    FitnessDataCreate,
    FitnessDataUpdate,
    FitnessDataResponse,
    FitnessDataListResponse,
    FitnessDailyResponse,
    FitnessSource,
)
from app.services.fitness_service import FitnessService
from app.core.database import get_db
import os

router = APIRouter(prefix="/api/fitness", tags=["Fitness"])


def get_current_user_id() -> int:
    """
    Get current user ID.
    TEMPORARY: Since no authentication system exists yet, this returns a configurable default.
    In production, this would come from authentication context.
    """
    # Use environment variable or default to 1 for testing
    return int(os.getenv("DEFAULT_USER_ID", "1"))


# ==================== Fitness Data Endpoints ====================

@router.post(
    "/",
    response_model=FitnessDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fitness data record",
    description="Create a new fitness data observation for the current user.",
)
async def create_fitness_data(
    fitness_data: FitnessDataCreate,
    db: Session = Depends(get_db)
) -> FitnessDataResponse:
    """Create a new fitness data record."""
    user_id = get_current_user_id()
    fitness_data.user_id = user_id  # Override with authenticated user

    service = FitnessService(db)
    fitness = service.create_fitness_data(fitness_data)

    return FitnessDataResponse.model_validate(fitness)


@router.get(
    "/",
    response_model=FitnessDataListResponse,
    summary="List fitness history",
    description="List all fitness data records for the current user with optional filtering.",
)
async def list_fitness_history(
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    source: Optional[FitnessSource] = Query(None, description="Filter by source"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
) -> FitnessDataListResponse:
    """List fitness history for the current user."""
    user_id = get_current_user_id()

    service = FitnessService(db)
    records = service.get_fitness_history(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        source=source.value if source else None,
    )

    return FitnessDataListResponse(
        fitness_data=[FitnessDataResponse.model_validate(r) for r in records],
        total=len(records)
    )


@router.get(
    "/daily",
    response_model=FitnessDailyResponse,
    summary="Get daily fitness summary",
    description="Get aggregated fitness data for a specific date.",
)
async def get_daily_fitness(
    target_date: Optional[date] = Query(None, description="Date for summary (defaults to today)"),
    db: Session = Depends(get_db)
) -> FitnessDailyResponse:
    """Get daily fitness summary for the current user."""
    user_id = get_current_user_id()
    target = target_date or date.today()

    service = FitnessService(db)
    return service.get_daily_summary(user_id, target)


@router.get(
    "/{fitness_id}",
    response_model=FitnessDataResponse,
    summary="Get a fitness record",
    description="Get a specific fitness data record by ID.",
)
async def get_fitness_data(
    fitness_id: int,
    db: Session = Depends(get_db)
) -> FitnessDataResponse:
    """Get a fitness data record by ID."""
    user_id = get_current_user_id()

    service = FitnessService(db)
    fitness = service.get_fitness_data(fitness_id, user_id)

    if not fitness:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fitness record {fitness_id} not found"
        )

    return FitnessDataResponse.model_validate(fitness)


@router.patch(
    "/{fitness_id}",
    response_model=FitnessDataResponse,
    summary="Update a fitness record",
    description="Update a fitness data record.",
)
async def update_fitness_data(
    fitness_id: int,
    fitness_data: FitnessDataUpdate,
    db: Session = Depends(get_db)
) -> FitnessDataResponse:
    """Update a fitness data record."""
    user_id = get_current_user_id()

    service = FitnessService(db)
    fitness = service.update_fitness_data(fitness_id, user_id, fitness_data)

    if not fitness:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fitness record {fitness_id} not found"
        )

    return FitnessDataResponse.model_validate(fitness)


@router.delete(
    "/{fitness_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a fitness record",
    description="Delete a fitness data record.",
)
async def delete_fitness_data(
    fitness_id: int,
    db: Session = Depends(get_db)
) -> None:
    """Delete a fitness data record."""
    user_id = get_current_user_id()

    service = FitnessService(db)
    success = service.delete_fitness_data(fitness_id, user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fitness record {fitness_id} not found"
        )


@router.get(
    "/stats/range",
    summary="Get fitness statistics for a date range",
    description="Get aggregated statistics for a date range.",
)
async def get_range_stats(
    start_date: date = Query(..., description="Start date for statistics"),
    end_date: date = Query(..., description="End date for statistics"),
    db: Session = Depends(get_db)
) -> dict:
    """Get fitness statistics for a date range."""
    user_id = get_current_user_id()

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date"
        )

    service = FitnessService(db)
    return service.get_date_range_stats(user_id, start_date, end_date)