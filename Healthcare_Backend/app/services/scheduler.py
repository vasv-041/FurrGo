"""
app/services/scheduler.py

Scheduler service for medication reminders using APScheduler.
"""
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional, List, Tuple
from contextlib import asynccontextmanager
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, engine
from app.models.medication import (
    Medication, 
    MedicationSchedule, 
    AdherenceLog, 
    AdherenceStatus,
    MedicationStatus
)
from app.services.events import ReminderEvent, emit_reminder_event, ReminderEvent

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Scheduler service for medication reminders.
    
    Uses APScheduler with SQLAlchemyJobStore for persistence.
    Manages medication reminder jobs based on MedicationSchedule.
    """
    
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._jobstore = None
    
    def initialize(self) -> None:
        """Initialize the scheduler with SQLAlchemy job store."""
        if self._scheduler is not None:
            return
        
        # Create job store using the existing engine
        self._jobstore = SQLAlchemyJobStore(engine=engine)
        
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": self._jobstore},
            job_defaults={
                "coalesce": True,  # Combine multiple missed runs into one
                "max_instances": 1,  # Don't run multiple instances of same job
                "misfire_grace_time": 300,  # 5 minutes grace period
            },
            timezone=timezone.utc,
        )
        
        logger.info("Scheduler service initialized")
    
    def start(self) -> None:
        """Start the scheduler and sync existing schedules."""
        if self._scheduler is None:
            self.initialize()
        
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")
    
    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("Scheduler shut down")
    
    @property
    def scheduler(self) -> Optional[AsyncIOScheduler]:
        return self._scheduler
    
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running


def _generate_job_id(medication_id: int, schedule_id: int, date_str: Optional[str] = None) -> str:
    """Generate a unique job ID for a medication schedule on a specific date."""
    if date_str:
        return f"med_{medication_id}_sched_{schedule_id}_{date_str}"
    return f"med_{medication_id}_sched_{schedule_id}"


def _parse_timezone(tz_str: str):
    """Parse timezone string to timezone object."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_str)
    except Exception:
        import pytz
        return pytz.timezone(tz_str)


def _get_next_run_time(
    time_of_day: time, 
    timezone_obj, 
    start_date: date, 
    end_date: date,
    from_date: date
) -> Optional[datetime]:
    """
    Calculate the next run time for a daily schedule.
    
    Returns the next datetime (in UTC) when the reminder should fire,
    or None if no valid run time exists within the date window.
    """
    # Start from the later of start_date and from_date
    current_date = max(start_date, from_date)
    
    # If we're past the end date, no more runs
    if current_date > end_date:
        return None
    
    # Create datetime in the schedule's timezone
    naive_dt = datetime.combine(current_date, time_of_day)
    
    # Localize to the schedule's timezone
    import pytz
    if hasattr(pytz, 'timezone'):
        try:
            tz = pytz.timezone(str(timezone))
            localized = tz.localize(naive_dt)
        except:
            import pytz
            tz = pytz.timezone('UTC')
            localized = tz.localize(naive_dt)
    else:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(str(timezone))
        localized = naive_dt.replace(tzinfo=tz)
    
    # Convert to UTC
    utc_time = localized.astimezone(timezone.utc)
    
    # If the time has already passed today, schedule for tomorrow
    if utc_time < datetime.now(timezone.utc):
        next_date = current_date + timedelta(days=1)
        if next_date > end_date:
            return None
        naive_dt = datetime.combine(next_date, time_of_day)
        import pytz
        if hasattr(pytz, 'timezone'):
            tz = pytz.timezone(str(timezone))
            localized = tz.localize(naive_dt)
        else:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(str(timezone))
            localized = naive_dt.replace(tzinfo=tz)
        utc_time = localized.astimezone(timezone.utc)
    
    return utc_time


def _create_reminder_job(
    scheduler,
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    time_of_day: time,
    timezone_str: str,
    start_date: date,
    end_date: date,
    user_id: int,
    from_date: date,
) -> Optional[str]:
    """
    Create a reminder job for a medication schedule.
    
    Returns the job ID if created, None if no valid run time.
    """
    # Get next run time
    run_time = _get_next_run_time(
        time_of_day=time_of_day,
        timezone_obj=timezone_str,
        start_date=medication_start_date,
        end_date=medication_end_date,
        from_date=from_date,
    )
    
    if run_time is None:
        return None
    
    # Generate unique job ID
    job_id = _generate_job_id(medication_id, schedule_id)
    
    # Create the trigger
    trigger = DateTrigger(run_date=run_time, timezone=timezone.utc)
    
    # Create the job
    scheduler.add_job(
        _execute_reminder,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        kwargs={
            "medication_id": medication_id,
            "schedule_id": schedule_id,
            "medication_name": medication_name,
            "dosage": dosage,
            "scheduled_time": scheduled_time,
            "user_id": user_id,
        },
    )
    
    logger.info(f"Created reminder job {job_id} for medication {medication_id} at {run_time.isoformat()}")
    return job_id


async def _execute_reminder(
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    scheduled_time: datetime,
    user_id: int,
) -> None:
    """
    Execute a reminder - emit the reminder event.
    
    This is called by APScheduler when a reminder fires.
    """
    import uuid
    
    event = ReminderEvent(
        medication_id=medication_id,
        schedule_id=schedule_id,
        medication_name=medication_name,
        dosage=dosage,
        scheduled_time=scheduled_time,
        user_id=user_id,
        event_id=str(uuid.uuid4()),
    )
    
    logger.info(f"Reminder fired: medication={medication_name} (id={medication_id}), user={user_id}")
    
    # Emit the event to registered callbacks
    from app.services.events import emit_reminder_event
    await emit_reminder_event(event)


# Global scheduler service instance
_scheduler_service: Optional["SchedulerService"] = None


def get_scheduler_service() -> "SchedulerService":
    """Get the global scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


async def sync_schedules_to_scheduler(db: Session) -> int:
    """
    Sync all active medication schedules to the scheduler.
    
    This should be called on startup to ensure all active schedules
    have corresponding jobs in the scheduler.
    
    Returns the number of jobs created/updated.
    """
    scheduler_service = get_scheduler_service()
    if not scheduler_service.scheduler:
        return 0
    
    scheduler = scheduler_service.scheduler
    count = 0
    
    from app.models.medication import Medication, MedicationSchedule
    from datetime import date
    
    today = date.today()
    
    # Query all active medications with active schedules
    schedules = db.execute(
        select(MedicationSchedule)
        .join(Medication)
        .where(
            MedicationSchedule.is_active == True,
            Medication.is_active == True,
            Medication.start_date <= date.today(),
            # Either no end date or end_date >= today
            (Medication.end_date.is_(None) | (Medication.end_date >= date.today()))
        )
    ).scalars().all()
    
    for schedule in schedules:
        medication = schedule.medication
        
        # Calculate date window
        start_date = medication.start_date
        end_date = medication.end_date if medication.end_date else date(2099, 12, 31)
        
        # Create/update job
        job_id = _create_reminder_job(
            scheduler=AsyncIOScheduler,  # We'll need the actual scheduler instance
            medication_id=medication.id,
            schedule_id=schedule.id,
            medication_name=medication.name,
            dosage=medication.dosage,
            time_of_day=schedule.time_of_day,
            timezone_str=schedule.timezone,
            start_date=medication.start_date,
            end_date=medication.end_date or date(2099, 12, 31),
            user_id=medication.user_id,
            from_date=date.today(),
        )
        
        if _create_reminder_job:
            count += 1
    
    return count


# Create the sync function that uses the actual scheduler
async def sync_schedules(db: Session) -> int:
    """Sync all active medication schedules to the scheduler."""
    from app.services.scheduler import get_scheduler_service
    
    scheduler_service = get_scheduler_service()
    if not scheduler_service.scheduler or not scheduler_service.scheduler.running:
        return 0
    
    scheduler = scheduler_service.scheduler
    count = 0
    
    from app.models.medication import Medication, MedicationSchedule
    from datetime import date
    
    today = date.today()
    
    # Query all active medications with active schedules
    schedules = db.execute(
        select(MedicationSchedule)
        .join(Medication)
        .where(
            MedicationSchedule.is_active == True,
            Medication.is_active == True,
            Medication.start_date <= date.today(),
            (Medication.end_date.is_(None) | (Medication.end_date >= date.today()))
        )
    ).scalars().all()
    
    for schedule in schedules:
        medication = schedule.medication
        
        # Create/update job for this schedule
        job_id = _create_or_update_job(
            scheduler=scheduler,
            medication_id=medication.id,
            schedule_id=schedule.id,
            medication_name=medication.name,
            dosage=medication.dosage,
            time_of_day=schedule.time_of_day,
            timezone_str=schedule.timezone,
            start_date=medication.start_date,
            end_date=medication.end_date or date(2099, 12, 31),
            user_id=medication.user_id,
        )
        
        if job_id:
            count += 1
    
    return count


def _create_or_update_job(
    scheduler,
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    time_of_day: time,
    timezone_str: str,
    start_date: date,
    end_date: date,
    user_id: int,
) -> Optional[str]:
    """Create or update a reminder job for a schedule."""
    # Calculate next run time
    today = date.today()
    run_time = _calculate_next_run(
        time_of_day=time_of_day,
        timezone_str=timezone_str,
        start_date=start_date,
        end_date=end_date,
        from_date=date.today(),
    )
    
    if run_time is None:
        return None
    
    job_id = f"med_{medication_id}_sched_{schedule_id}"
    
    # Create the trigger
    trigger = DateTrigger(run_date=run_time, timezone=timezone.utc)
    
    # Import here to avoid circular imports
    import uuid
    
    scheduler.add_job(
        _execute_reminder_job,
        trigger=trigger,
        id=f"med_{medication_id}_sched_{schedule_id}",
        replace_existing=True,
        kwargs={
            "medication_id": medication_id,
            "schedule_id": schedule_id,
            "medication_name": medication_name,
            "dosage": dosage,
            "scheduled_time": run_time,
            "user_id": user_id,
        },
    )
    
    logger.info(f"Created/updated reminder job for medication {medication_id}, schedule {schedule_id} at {run_time.isoformat()}")
    return f"med_{medication_id}_sched_{schedule_id}"


async def _execute_reminder_job(
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    scheduled_time: datetime,
    user_id: int,
) -> None:
    """Execute a reminder job - emit the reminder event."""
    import uuid
    
    event = ReminderEvent(
        medication_id=medication_id,
        schedule_id=schedule_id,
        medication_name=medication_name,
        dosage=dosage,
        scheduled_time=scheduled_time,
        user_id=user_id,
        event_id=str(uuid.uuid4()),
    )
    
    logger.info(f"Reminder fired: medication={medication_name} (id={medication_id}), user={user_id}")
    
    from app.services.events import emit_reminder_event
    await emit_reminder_event(event)


# Scheduler instance for module-level access
_scheduler_instance: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance."""
    global _scheduler_instance
    return _scheduler_instance


def initialize_scheduler() -> AsyncIOScheduler:
    """Initialize the global scheduler instance."""
    global _scheduler_instance
    
    if _scheduler_instance is not None:
        return _scheduler_instance
    
    jobstore = SQLAlchemyJobStore(engine=engine)
    
    _scheduler_instance = AsyncIOScheduler(
        jobstores={"default": jobstore},
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
        timezone=timezone.utc,
    )
    
    return _scheduler_instance


def start_scheduler() -> None:
    """Start the global scheduler."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = initialize_scheduler()
    if not _scheduler_instance.running:
        _scheduler_instance.start()


def shutdown_scheduler() -> None:
    """Shutdown the global scheduler."""
    global _scheduler_instance
    if _scheduler_instance and _scheduler_instance.running:
        _scheduler_instance.shutdown(wait=True)
        _scheduler_instance = None


def schedule_medication(
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    time_of_day: time,
    timezone_str: str,
    start_date: date,
    end_date: date,
    user_id: int,
) -> Optional[str]:
    """Schedule a medication reminder."""
    # This will be implemented with the actual scheduler
    pass