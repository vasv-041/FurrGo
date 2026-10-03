"""
app/services/scheduler.py

Scheduler service for medication reminders using APScheduler.
"""
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional
import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.core.database import engine
from app.models.medication import Medication, MedicationSchedule
from app.services.events import ReminderEvent, emit_reminder_event

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Scheduler service for medication reminders.
    
    Uses APScheduler with SQLAlchemyJobStore for persistence.
    Manages medication reminder jobs based on MedicationSchedule.
    """
    
    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None
    
    def initialize(self) -> None:
        """Initialize the scheduler with SQLAlchemy job store."""
        if self._scheduler is not None:
            return
        
        # Create job store using the existing engine
        jobstore = SQLAlchemyJobStore(engine=engine)
        
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": jobstore},
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
            timezone=timezone.utc,
        )
        
        logger.info("Scheduler service initialized")
    
    def start(self) -> None:
        """Start the scheduler."""
        if self._scheduler is None:
            self.initialize()
        
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")
    
    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            self._scheduler = None
            logger.info("Scheduler shut down")
    
    @property
    def scheduler(self) -> AsyncIOScheduler | None:
        return self._scheduler
    
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running


# Global scheduler service instance
_scheduler_service: "SchedulerService | None" = None


def get_scheduler_service() -> "SchedulerService":
    """Get the global scheduler service instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


def _generate_job_id(medication_id: int, schedule_id: int) -> str:
    """Generate a unique job ID for a medication schedule."""
    return f"med_{medication_id}_sched_{schedule_id}"


def _calculate_next_run(
    time_of_day: time,
    timezone_str: str,
    start_date: date,
    end_date: date,
    from_date: date,
) -> datetime | None:
    """
    Calculate the next run time for a daily schedule.
    
    Returns the next datetime (in UTC) when the reminder should fire,
    or None if no valid run time exists within the date window.
    """
    # Start from the later of start_date and today
    current_date = max(start_date, date.today())
    
    # If we're past the end date, no more runs
    if current_date > end_date:
        return None
    
    # Create datetime in the schedule's timezone
    naive_dt = datetime.combine(current_date, time_of_day)
    
    # Localize to the schedule's timezone
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone_str)
        localized = naive_dt.replace(tzinfo=tz)
    except Exception:
        import pytz
        tz = pytz.timezone(timezone_str)
        localized = tz.localize(naive_dt)
    
    # Convert to UTC
    utc_time = localized.astimezone(timezone.utc)
    
    # If the time has already passed today, schedule for tomorrow
    if utc_time < datetime.now(timezone.utc):
        next_date = current_date + timedelta(days=1)
        if next_date > end_date:
            return None
        naive_dt = datetime.combine(next_date, time_of_day)
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone_str)
            localized = naive_dt.replace(tzinfo=tz)
        except Exception:
            import pytz
            tz = pytz.timezone(timezone_str)
            localized = tz.localize(naive_dt)
        utc_time = localized.astimezone(timezone.utc)
    
    return utc_time


async def _execute_reminder_job(
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    scheduled_time: datetime,
    user_id: int,
) -> None:
    """Execute a reminder job - emit the reminder event."""
    
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


def _create_or_update_job(
    scheduler: AsyncIOScheduler,
    medication_id: int,
    schedule_id: int,
    medication_name: str,
    dosage: Optional[str],
    time_of_day: time,
    timezone_str: str,
    start_date: date,
    end_date: date,
    user_id: int,
) -> str | None:
    """Create or update a reminder job for a schedule."""
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
    
    scheduler.add_job(
        _execute_reminder_job,
        trigger=trigger,
        id=job_id,
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
    return job_id


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
) -> str | None:
    """Schedule a medication reminder."""
    from app.services.scheduler import get_scheduler_service
    
    scheduler_service = get_scheduler_service()
    scheduler = scheduler_service.scheduler
    
    if not scheduler or not scheduler.running:
        logger.warning("Scheduler not running, cannot schedule medication")
        return None
    
    return _create_or_update_job(
        scheduler=scheduler,
        medication_id=medication_id,
        schedule_id=schedule_id,
        medication_name=medication_name,
        dosage=dosage,
        time_of_day=time_of_day,
        timezone_str=timezone_str,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
    )


async def sync_schedules(db) -> int:
    """
    Sync all active medication schedules to the scheduler.
    
    This should be called on startup to ensure all active schedules
    have corresponding jobs in the scheduler.
    
    Returns the number of jobs created/updated.
    """
    from app.models.medication import Medication, MedicationSchedule
    from sqlalchemy import select
    from datetime import date
    from app.core.database import get_db

    scheduler_service = get_scheduler_service()
    scheduler = scheduler_service.scheduler

    if not scheduler or not scheduler.running:
        logger.warning("Scheduler not running, cannot sync schedules")
        return 0

    # Get a database session
    db_session = next(get_db())

    try:
        schedules = db_session.execute(
            select(MedicationSchedule)
            .join(Medication)
            .where(
                MedicationSchedule.is_active == True,
                Medication.is_active == True,
                Medication.start_date <= date.today(),
                (Medication.end_date.is_(None) | (Medication.end_date >= date.today()))
            )
        ).scalars().all()

        count = 0
        for schedule in schedules:
            medication = schedule.medication

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
    finally:
        db_session.close()


def remove_schedule_job(schedule_id: int, medication_id: int) -> bool:
    """Remove a schedule's job from the scheduler."""
    scheduler_service = get_scheduler_service()
    scheduler = scheduler_service.scheduler

    if not scheduler or not scheduler.running:
        logger.warning("Scheduler not running, cannot remove job")
        return False

    job_id = f"med_{medication_id}_sched_{schedule_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed job {job_id}")
        return True
    except Exception as e:
        logger.warning(f"Job {job_id} not found or could not be removed: {e}")
        return False


def remove_medication_jobs(medication_id: int) -> int:
    """Remove all jobs for a medication."""
    scheduler_service = get_scheduler_service()
    scheduler = scheduler_service.scheduler

    if not scheduler or not scheduler.running:
        logger.warning("Scheduler not running, cannot remove jobs")
        return 0

    # Get all jobs matching the medication prefix
    job_prefix = f"med_{medication_id}_sched_"
    removed = 0
    for job in scheduler.get_jobs():
        if job.id.startswith(job_prefix):
            try:
                scheduler.remove_job(job.id)
                logger.info(f"Removed job {job.id}")
                removed += 1
            except Exception as e:
                logger.warning(f"Job {job.id} could not be removed: {e}")

    return removed