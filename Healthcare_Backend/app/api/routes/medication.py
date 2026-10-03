"""
app/api/routes/medication.py

Medication management API routes for Phase 7A.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session

from app.schemas.medication import (
    MedicationCreate,
    MedicationUpdate,
    MedicationResponse,
    MedicationScheduleCreate,
    MedicationScheduleUpdate,
    MedicationScheduleResponse,
    AdherenceLogCreate,
    AdherenceLogResponse,
    AdherenceSummaryResponse,
    MedicationListResponse,
)
from app.services.medication_service import MedicationService
from app.core.database import get_db
from app.core.config import settings

router = APIRouter(prefix="/api/medications", tags=["Medications"])


def get_current_user_id() -> int:
    """
    Get current user ID.
    TEMPORARY: Since no authentication system exists yet, this returns a configurable default.
    In production, this would come from authentication context.
    """
    # Use environment variable or default to 1 for testing
    import os
    return int(os.getenv("DEFAULT_USER_ID", "1"))


# ==================== Medication Endpoints ====================

@router.post(
    "/",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new medication",
    description="Create a new medication for the current user.",
)
async def create_medication(
    medication_data: MedicationCreate,
    db: Session = Depends(get_db)
) -> MedicationResponse:
    """Create a new medication."""
    user_id = get_current_user_id()
    
    service = MedicationService(db)
    medication = service.create_medication(user_id, medication_data)
    
    return MedicationResponse.model_validate(medication)


@router.get(
    "/",
    response_model=MedicationListResponse,
    summary="List medications",
    description="List all medications for the current user.",
)
async def list_medications(
    active_only: bool = Query(True, description="Only return active medications"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
) -> MedicationListResponse:
    """List medications for the current user."""
    user_id = get_current_user_id()
    
    service = MedicationService(db)
    medications = service.list_medications(
        user_id=user_id,
        active_only=active_only,
        limit=limit,
        offset=offset
    )
    
    return MedicationListResponse(
        medications=[MedicationResponse.model_validate(m) for m in medications],
        total=len(medications)
    )


@router.get(
    "/{medication_id}",
    response_model=MedicationResponse,
    summary="Get a medication",
    description="Get a specific medication by ID.",
)
async def get_medication(
    medication_id: int,
    db: Session = Depends(get_db)
) -> MedicationResponse:
    """Get a medication by ID."""
    user_id = get_current_user_id()
    
    service = MedicationService(db)
    medication = service.get_medication(medication_id, user_id)
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return MedicationResponse.model_validate(medication)


@router.patch(
    "/{medication_id}",
    response_model=MedicationResponse,
    summary="Update a medication",
    description="Update a medication's details.",
)
async def update_medication(
    medication_id: int,
    medication_data: MedicationUpdate,
    db: Session = Depends(get_db)
) -> MedicationResponse:
    """Update a medication."""
    user_id = get_current_user_id()
    
    service = MedicationService(db)
    medication = service.update_medication(medication_id, get_current_user_id(), medication_data)
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return MedicationResponse.model_validate(medication)


@router.delete(
    "/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a medication",
    description="Hard delete a medication and all its schedules/logs.",
)
async def delete_medication(
    medication_id: int,
    db: Session = Depends(get_db)
) -> None:
    """Delete a medication (hard delete)."""
    success = MedicationService(db).delete_medication(medication_id, get_current_user_id())
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )


@router.patch(
    "/{medication_id}/deactivate",
    response_model=MedicationResponse,
    summary="Deactivate a medication",
    description="Soft delete a medication (set is_active to false).",
)
async def deactivate_medication(
    medication_id: int,
    db: Session = Depends(get_db)
) -> MedicationResponse:
    """Deactivate a medication (soft delete)."""
    medication = MedicationService(db).deactivate_medication(medication_id, get_current_user_id())
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return MedicationResponse.model_validate(medication)


# ==================== Schedule Endpoints ====================

@router.post(
    "/{medication_id}/schedules",
    response_model=MedicationScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a medication schedule",
    description="Create a reminder schedule for a medication.",
)
async def create_schedule(
    medication_id: int,
    schedule_data: "MedicationScheduleCreate",
    db: Session = Depends(get_db)
) -> MedicationScheduleResponse:
    """Create a medication schedule."""
    from app.schemas.medication import MedicationScheduleCreate
    
    user_id = get_current_user_id()
    service = MedicationService(db)
    schedule = service.create_schedule(medication_id, get_current_user_id(), schedule_data)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return MedicationScheduleResponse.model_validate(schedule)


@router.get(
    "/{medication_id}/schedules",
    response_model=List[MedicationScheduleResponse],
    summary="Get medication schedules",
    description="Get all schedules for a medication.",
)
async def get_schedules(
    medication_id: int,
    db: Session = Depends(get_db)
) -> List[MedicationScheduleResponse]:
    """Get all schedules for a medication."""
    user_id = get_current_user_id()
    service = MedicationService(db)
    medication = service.get_medication(medication_id, user_id)
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    schedules = service.get_schedules(medication_id)
    return [MedicationScheduleResponse.model_validate(s) for s in schedules]


@router.patch(
    "/{medication_id}/schedules/{schedule_id}",
    response_model=MedicationScheduleResponse,
    summary="Update a schedule",
    description="Update a medication schedule.",
)
async def update_schedule(
    medication_id: int,
    schedule_id: int,
    schedule_data: "MedicationScheduleUpdate",
    db: Session = Depends(get_db)
) -> MedicationScheduleResponse:
    """Update a medication schedule."""
    from app.schemas.medication import MedicationScheduleUpdate
    
    user_id = get_current_user_id()
    service = MedicationService(db)
    schedule = service.update_schedule(schedule_id, medication_id, get_current_user_id(), schedule_data)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )
    
    return MedicationScheduleResponse.model_validate(schedule)


@router.patch(
    "/{medication_id}/schedules/{schedule_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a schedule",
    description="Deactivate a medication schedule.",
)
async def deactivate_schedule(
    medication_id: int,
    schedule_id: int,
    db: Session = Depends(get_db)
) -> None:
    """Deactivate a medication schedule."""
    service = MedicationService(db)
    success = service.deactivate_schedule(schedule_id, medication_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found"
        )


# ==================== Adherence Endpoints ====================

@router.post(
    "/{medication_id}/adherence",
    response_model=AdherenceLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record adherence",
    description="Record a medication adherence log entry.",
)
async def create_adherence_log(
    medication_id: int,
    adherence_data: "AdherenceLogCreate",
    db: Session = Depends(get_db)
) -> AdherenceLogResponse:
    """Record an adherence log entry."""
    from app.schemas.medication import AdherenceLogCreate
    
    user_id = get_current_user_id()
    service = MedicationService(db)
    log = service.create_adherence_log(medication_id, get_current_user_id(), adherence_data)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return AdherenceLogResponse.model_validate(log)


@router.get(
    "/{medication_id}/adherence",
    response_model=List[AdherenceLogResponse],
    summary="Get adherence logs",
    description="Get adherence logs for a medication.",
)
async def get_adherence_logs(
    medication_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
) -> List[AdherenceLogResponse]:
    """Get adherence logs for a medication."""
    user_id = get_current_user_id()
    service = MedicationService(db)
    medication = service.get_medication(medication_id, user_id)
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    logs = service.get_adherence_logs(medication_id, user_id, start_date, end_date, limit, offset)
    return [AdherenceLogResponse.model_validate(log) for log in logs]


@router.get(
    "/{medication_id}/adherence/summary",
    response_model=AdherenceSummaryResponse,
    summary="Get adherence summary",
    description="Get adherence percentage and counts for a medication.",
)
async def get_adherence_summary(
    medication_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db)
) -> AdherenceSummaryResponse:
    """Get adherence summary for a medication."""
    user_id = get_current_user_id()
    service = MedicationService(db)
    medication = service.get_medication(medication_id, user_id)
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    summary = service.calculate_adherence_percentage(medication_id, user_id, start_date, end_date)
    return summary