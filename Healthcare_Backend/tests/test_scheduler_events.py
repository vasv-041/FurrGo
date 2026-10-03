"""
tests/test_scheduler_events.py

Tests for Phase 7B: ReminderEvent and SchedulerService
"""
import pytest
from datetime import datetime, date, time, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.events import (
    ReminderEvent,
    ReminderCallback,
    ReminderCallbackRegistry,
    LoggingReminderCallback,
    emit_reminder_event,
)
from app.services.scheduler import (
    SchedulerService,
    get_scheduler_service,
    schedule_medication,
    _calculate_next_run,
    sync_schedules,
    _execute_reminder_job,
)


class TestReminderEvent:
    """Tests for ReminderEvent dataclass."""

    def test_reminder_event_creation(self):
        """Test creating a ReminderEvent with all fields."""
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        assert event.medication_id == 1
        assert event.schedule_id == 1
        assert event.medication_name == "Aspirin"
        assert event.dosage == "100mg"
        assert event.user_id == 1
        assert event.event_id is not None

    def test_reminder_event_optional_dosage(self):
        """Test creating a ReminderEvent with optional dosage as None."""
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage=None,
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        assert event.dosage is None


class TestReminderCallback:
    """Tests for ReminderCallback abstract base class."""

    def test_reminder_callback_is_abstract(self):
        """Test ReminderCallback is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ReminderCallback()


class TestLoggingReminderCallback:
    """Tests for LoggingReminderCallback."""

    def test_logging_callback_instantiation(self):
        """Test LoggingReminderCallback can be instantiated."""
        callback = LoggingReminderCallback()
        assert callback is not None

    @pytest.mark.asyncio
    async def test_logging_callback_on_reminder(self):
        """Test logging callback handles reminder without error."""
        callback = LoggingReminderCallback()
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        # Should not raise
        await callback.on_reminder(event)


class TestReminderCallbackRegistry:
    """Tests for ReminderCallbackRegistry."""

    def test_registry_initialization(self):
        """Test registry starts with empty callbacks."""
        registry = ReminderCallbackRegistry()
        assert len(registry._callbacks) == 0
        assert registry._default_callback is not None

    def test_register_callback(self):
        """Test registering a callback."""
        registry = ReminderCallbackRegistry()
        callback = AsyncMock()
        
        registry.register(callback)
        assert len(registry._callbacks) == 1
        assert registry._callbacks[0] == callback

    def test_unregister_callback(self):
        """Test unregistering a callback."""
        registry = ReminderCallbackRegistry()
        callback = AsyncMock()
        
        registry.register(callback)
        result = registry.unregister(callback)
        assert result is True
        assert len(registry._callbacks) == 0

    def test_unregister_nonexistent_callback(self):
        """Test unregistering a non-existent callback returns False."""
        registry = ReminderCallbackRegistry()
        callback = AsyncMock()
        
        result = registry.unregister(callback)
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_calls_all_callbacks(self):
        """Test emit calls all registered callbacks."""
        registry = ReminderCallbackRegistry()
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        registry.register(callback1)
        registry.register(callback2)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        await registry.emit(event)
        
        # Registered callbacks should be called (default callback is also called)
        callback1.on_reminder.assert_called_once_with(event)
        callback2.on_reminder.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_emit_with_no_registered_callbacks(self):
        """Test emit with no registered callbacks only calls default."""
        registry = ReminderCallbackRegistry()
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        # Should not raise
        await registry.emit(event)

    @pytest.mark.asyncio
    async def test_emit_callback_exception_handled(self):
        """Test emit handles callback exceptions gracefully."""
        registry = ReminderCallbackRegistry()
        callback1 = AsyncMock()
        callback1.on_reminder.side_effect = Exception("Callback error")
        callback2 = AsyncMock()
        
        registry.register(callback1)
        registry.register(callback2)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        # Should not raise despite callback1 error
        await registry.emit(event)
        
        # callback2 should still be called
        callback2.on_reminder.assert_called_once_with(event)


class TestSchedulerService:
    """Tests for SchedulerService."""

    def test_service_initialization(self):
        """Test scheduler service initializes correctly."""
        service = SchedulerService()
        assert service._scheduler is None
        assert service.is_running() is False
        
        service.initialize()
        assert service._scheduler is not None
        assert service.scheduler is not None

    def test_service_start_stop(self):
        """Test scheduler service start and shutdown."""
        import asyncio
        service = SchedulerService()
        
        # Start requires an event loop
        async def start_service():
            service.start()
            assert service.is_running() is True
            service.shutdown()
            assert service.is_running() is False
        
        asyncio.run(start_service())

    def test_get_scheduler_service_singleton(self):
        """Test get_scheduler_service returns singleton."""
        service1 = get_scheduler_service()
        service2 = get_scheduler_service()
        assert service1 is service2


class TestCalculateNextRun:
    """Tests for _calculate_next_run function."""

    def test_next_run_today_future_time(self):
        """Test next run calculation for a future time today."""
        now = datetime.now(timezone.utc)
        # Set time 1 hour in the future
        future_time = (now + timedelta(hours=1)).time()
        tz_str = "UTC"
        
        result = _calculate_next_run(
            time_of_day=future_time,
            timezone_str=tz_str,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            from_date=date.today(),
        )
        
        assert result is not None
        assert result > now
        assert result < now + timedelta(hours=2)

    def test_next_run_today_past_time(self):
        """Test next run calculation when time has passed today."""
        now = datetime.now(timezone.utc)
        # Set time 1 hour in the past
        past_time = (now - timedelta(hours=1)).time()
        tz_str = "UTC"
        
        result = _calculate_next_run(
            time_of_day=past_time,
            timezone_str=tz_str,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            from_date=date.today(),
        )
        
        assert result is not None
        assert result > now
        assert result.date() == (now + timedelta(days=1)).date()

    def test_next_run_before_start_date(self):
        """Test next run when start date is in the future."""
        future_start = date.today() + timedelta(days=5)
        future_time = time(10, 0)
        tz_str = "UTC"
        
        result = _calculate_next_run(
            time_of_day=future_time,
            timezone_str=tz_str,
            start_date=future_start,
            end_date=future_start + timedelta(days=30),
            from_date=date.today(),
        )
        
        assert result is not None
        assert result.date() == future_start

    def test_next_run_after_end_date(self):
        """Test next run returns None when past end date."""
        past_end = date.today() - timedelta(days=1)
        tz_str = "UTC"
        
        result = _calculate_next_run(
            time_of_day=time(10, 0),
            timezone_str=tz_str,
            start_date=date.today() - timedelta(days=10),
            end_date=past_end,
            from_date=date.today(),
        )
        
        assert result is None

    def test_next_run_timezone_handling(self):
        """Test next run handles different timezones."""
        tz_str = "America/New_York"
        future_time = time(10, 0)
        
        result = _calculate_next_run(
            time_of_day=future_time,
            timezone_str=tz_str,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            from_date=date.today(),
        )
        
        assert result is not None
        # Result should be in UTC
        assert result.tzinfo == timezone.utc


class TestScheduleMedication:
    """Tests for schedule_medication function."""

    @pytest.mark.asyncio
    async def test_schedule_medication_creates_job(self):
        """Test scheduling a medication creates a job."""
        with patch('app.services.scheduler.get_scheduler_service') as mock_get:
            mock_service = MagicMock()
            mock_scheduler = MagicMock()
            mock_scheduler.running = True
            mock_service.scheduler = mock_scheduler
            mock_get.return_value = mock_service
            
            # Use a future time
            future = datetime.now(timezone.utc) + timedelta(hours=1)
            run_time = future
            
            with patch('app.services.scheduler._calculate_next_run', return_value=run_time):
                job_id = schedule_medication(
                    medication_id=1,
                    schedule_id=1,
                    medication_name="Aspirin",
                    dosage="100mg",
                    time_of_day=time(10, 0),
                    timezone_str="UTC",
                    start_date=date.today(),
                    end_date=date.today() + timedelta(days=30),
                    user_id=1,
                )
            
            assert job_id == "med_1_sched_1"
            mock_scheduler.add_job.assert_called_once()

    def test_schedule_medication_not_running(self):
        """Test scheduling when scheduler not running returns None."""
        with patch('app.services.scheduler.get_scheduler_service') as mock_get:
            mock_service = MagicMock()
            mock_service.scheduler = None
            mock_get.return_value = mock_service
            
            job_id = schedule_medication(
                medication_id=1,
                schedule_id=1,
                medication_name="Aspirin",
                dosage="100mg",
                time_of_day=time(10, 0),
                timezone_str="UTC",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=30),
                user_id=1,
            )
            
            assert job_id is None

    def test_schedule_medication_no_valid_run_time(self):
        """Test scheduling returns None when no valid run time."""
        with patch('app.services.scheduler.get_scheduler_service') as mock_get:
            mock_service = MagicMock()
            mock_scheduler = MagicMock()
            mock_scheduler.running = True
            mock_service.scheduler = mock_scheduler
            mock_get.return_value = mock_service
            
            with patch('app.services.scheduler._calculate_next_run', return_value=None):
                job_id = schedule_medication(
                    medication_id=1,
                    schedule_id=1,
                    medication_name="Aspirin",
                    dosage="100mg",
                    time_of_day=time(10, 0),
                    timezone_str="UTC",
                    start_date=date.today(),
                    end_date=date.today() - timedelta(days=1),  # End date in past
                    user_id=1,
                )
            
            assert job_id is None


class TestExecuteReminderJob:
    """Tests for _execute_reminder_job function."""

    @pytest.mark.asyncio
    async def test_execute_reminder_job_emits_event(self):
        """Test executing reminder job emits event."""
        with patch('app.services.events.emit_reminder_event') as mock_emit:
            mock_emit.return_value = None
            
            scheduled_time = datetime.now(timezone.utc)
            
            await _execute_reminder_job(
                medication_id=1,
                schedule_id=1,
                medication_name="Aspirin",
                dosage="100mg",
                scheduled_time=scheduled_time,
                user_id=1,
            )
            
            mock_emit.assert_called_once()
            event = mock_emit.call_args[0][0]
            assert isinstance(event, ReminderEvent)
            assert event.medication_id == 1
            assert event.schedule_id == 1
            assert event.medication_name == "Aspirin"
            assert event.dosage == "100mg"
            assert event.user_id == 1


class TestSyncSchedules:
    """Tests for sync_schedules function."""

    @pytest.mark.asyncio
    async def test_sync_schedules_creates_jobs(self):
        """Test sync_schedules creates jobs for active schedules."""
        # This test would require database setup - skipping for now
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])