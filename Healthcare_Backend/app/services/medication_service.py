"""
app/services/medication_service.py

Business logic for medication management.
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.medication import (
    Medication, 
    MedicationSchedule, 
    AdherenceLog, 
    AdherenceStatus
)
from app.services.scheduler import remove_schedule_job, remove_medication_jobs
from app.schemas.medication import (
    MedicationCreate,
    MedicationUpdate,
    MedicationScheduleCreate,
    MedicationScheduleUpdate,
    AdherenceLogCreate,
    AdherenceSummaryResponse
)


class MedicationService:
    """Service layer for medication management."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Medication CRUD ====================

    def create_medication(self, user_id: int, medication_data: MedicationCreate) -> "Medication":
        """Create a new medication for a user."""
        medication = Medication(
            user_id=user_id,
            name=medication_data.name.strip(),
            dosage=medication_data.dosage.strip() if medication_data.dosage else None,
            frequency=medication_data.frequency.strip(),
            start_date=medication_data.start_date,
            end_date=medication_data.end_date,
            notes=medication_data.notes.strip() if medication_data.notes else None,
            is_active=medication_data.is_active,
        )
        self.db.add(medication)
        self.db.commit()
        self.db.refresh(medication)
        return medication

    def get_medication(self, medication_id: int, user_id: Optional[int] = None) -> Optional["Medication"]:
        """Get a medication by ID, optionally filtered by user."""
        query = self.db.query(Medication).filter(Medication.id == medication_id)
        if user_id is not None:
            query = query.filter(Medication.user_id == user_id)
        return query.first()

    def list_medications(
        self, 
        user_id: Optional[int] = None, 
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List["Medication"]:
        """List medications with optional filtering."""
        query = self.db.query(Medication)
        
        if user_id is not None:
            query = query.filter(Medication.user_id == user_id)
        if active_only:
            query = query.filter(Medication.is_active == True)
        
        return query.order_by(Medication.created_at.desc()).limit(limit).offset(offset).all()

    def update_medication(
        self, 
        medication_id: int, 
        user_id: int, 
        update_data: MedicationUpdate
    ) -> Optional["Medication"]:
        """Update a medication."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if field in ["name", "frequency", "dosage", "notes"] and isinstance(value, str):
                value = value.strip()
            setattr(medication, field, value)
        
        medication.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(medication)
        return medication

    def deactivate_medication(self, medication_id: int, user_id: int) -> Optional["Medication"]:
            """Deactivate (soft delete) a medication."""
            medication = self.get_medication(medication_id, user_id)
            if not medication:
                return None

            medication.is_active = False
            medication.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(medication)

            # Remove all associated scheduler jobs
            remove_medication_jobs(medication_id)

            return medication

    def delete_medication(self, medication_id: int, user_id: int) -> bool:
        """Hard delete a medication (and cascaded schedules/logs)."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return False
        
        self.db.delete(medication)
        self.db.commit()
        return True

    # ==================== Medication Schedules ====================

    def create_schedule(
        self, 
        medication_id: int, 
        user_id: int, 
        schedule_data: "MedicationScheduleCreate"
    ) -> Optional["MedicationSchedule"]:
        """Create a medication schedule."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return None
        
        schedule = MedicationSchedule(
            medication_id=medication_id,
            time_of_day=schedule_data.time_of_day,
            timezone=schedule_data.timezone.strip(),
            is_active=schedule_data.is_active,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def get_schedules(self, medication_id: int) -> List["MedicationSchedule"]:
        """Get all schedules for a medication."""
        return self.db.query(MedicationSchedule).filter(
            MedicationSchedule.medication_id == medication_id
        ).all()

    def update_schedule(
        self, 
        schedule_id: int, 
        medication_id: int, 
        user_id: int,
        update_data: "MedicationScheduleUpdate"
    ) -> Optional["MedicationSchedule"]:
        """Update a medication schedule."""
        schedule = self.db.query(MedicationSchedule).filter(
            MedicationSchedule.id == schedule_id,
            MedicationSchedule.medication_id == medication_id
        ).first()
        
        if not schedule:
            return None
        
        # Verify ownership
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if field == "timezone" and isinstance(value, str):
                value = value.strip()
            setattr(schedule, field, value)
        
        schedule.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def deactivate_schedule(self, schedule_id: int, medication_id: int) -> bool:
            """Deactivate a schedule."""
            schedule = self.db.query(MedicationSchedule).filter(
                MedicationSchedule.id == schedule_id,
                MedicationSchedule.medication_id == medication_id
            ).first()
            if not schedule:
                return False

            schedule.is_active = False
            schedule.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            # Remove the associated scheduler job
            remove_schedule_job(schedule_id, medication_id)

            return True

    # ==================== Adherence Logs ====================

    def create_adherence_log(
        self, 
        medication_id: int, 
        user_id: int, 
        log_data: "AdherenceLogCreate"
    ) -> Optional[AdherenceLog]:
        """Create an adherence log entry."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return None
        
        log = AdherenceLog(
            medication_id=medication_id,
            scheduled_time=log_data.scheduled_time,
            status=AdherenceStatus(log_data.status),
            notes=log_data.notes.strip() if log_data.notes else None,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_adherence_logs(
        self, 
        medication_id: int, 
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AdherenceLog]:
        """Retrieve adherence logs for a medication."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            return []
        
        query = self.db.query(AdherenceLog).filter(
            AdherenceLog.medication_id == medication_id
        )
        
        if start_date:
            query = query.filter(AdherenceLog.scheduled_time >= start_date)
        if end_date:
            query = query.filter(AdherenceLog.scheduled_time <= end_date)
        
        return query.order_by(AdherenceLog.scheduled_time.desc()).limit(limit).offset(offset).all()

    def calculate_adherence_percentage(
        self, 
        medication_id: int, 
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AdherenceSummaryResponse:
        """Calculate adherence percentage from stored logs."""
        medication = self.get_medication(medication_id, user_id)
        if not medication:
            raise ValueError("Medication not found")
        
        query = self.db.query(AdherenceLog).filter(
            AdherenceLog.medication_id == medication_id
        )
        
        if start_date:
            query = query.filter(AdherenceLog.scheduled_time >= start_date)
        if end_date:
            query = query.filter(AdherenceLog.scheduled_time <= end_date)
        
        logs = query.all()
        
        if not logs:
            return AdherenceSummaryResponse(
                medication_id=medication_id,
                total_logs=0,
                taken_count=0,
                missed_count=0,
                snoozed_count=0,
                adherence_percentage=0.0,
                period_start=start_date,
                period_end=end_date
            )
        
        taken = sum(1 for log in logs if log.status == AdherenceStatus.TAKEN)
        missed = sum(1 for log in logs if log.status == AdherenceStatus.MISSED)
        snoozed = sum(1 for log in logs if log.status == AdherenceStatus.SNOOZED)
        total = len(logs)
        
        percentage = (taken / total * 100) if total > 0 else 0.0
        
        return AdherenceSummaryResponse(
            medication_id=medication_id,
            total_logs=total,
            taken_count=taken,
            missed_count=missed,
            snoozed_count=snoozed,
            adherence_percentage=round(percentage, 2),
            period_start=min(log.scheduled_time for log in logs) if logs else None,
            period_end=max(log.scheduled_time for log in logs) if logs else None
        )