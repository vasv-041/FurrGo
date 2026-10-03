"""
app/services/events.py

Event definitions and callback interface for Phase 7B scheduler.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class ReminderEvent:
    """
    Event emitted when a medication reminder fires.
    
    This is the contract between the scheduler and any notification
    delivery mechanism. The scheduler emits this event; a notification
    service (to be implemented in a later phase) consumes it.
    """
    medication_id: int
    schedule_id: int
    medication_name: str
    dosage: Optional[str]
    scheduled_time: datetime  # UTC
    user_id: int
    event_id: str  # Unique ID for this firing (e.g., for deduplication)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "medication_id": self.medication_id,
            "schedule_id": self.schedule_id,
            "medication_name": self.medication_name,
            "dosage": self.dosage,
            "scheduled_time": self.scheduled_time.isoformat(),
            "user_id": self.user_id,
            "event_id": self.event_id,
        }


class ReminderCallback(ABC):
    """
    Abstract base class for reminder delivery.
    
    Implement this to handle reminder events. The scheduler will call
    `on_reminder` when a medication reminder fires.
    """
    
    @abstractmethod
    async def on_reminder(self, event: ReminderEvent) -> None:
        """
        Handle a reminder event.
        
        Args:
            event: The ReminderEvent that fired.
        """
        pass


class LoggingReminderCallback(ReminderCallback):
    """
    Default callback that logs reminder events.
    
    Used as the default when no notification service is configured.
    """
    
    def __init__(self):
        import logging
        self._logger = logging.getLogger(__name__)
    
    async def on_reminder(self, event: ReminderEvent) -> None:
        self._logger.info(
            "Reminder fired: medication=%s (id=%d), schedule=%d, time=%s, user=%d",
            event.medication_name,
            event.medication_id,
            event.schedule_id,
            event.scheduled_time.isoformat(),
            event.user_id,
        )


# Global callback registry (simple pub/sub)
class ReminderCallbackRegistry:
    """
    Registry for reminder callbacks.
    
    Allows registering multiple callbacks that will all be notified
    when a reminder fires.
    """
    
    def __init__(self):
        self._callbacks: list[ReminderCallback] = []
        self._default_callback = LoggingReminderCallback()
    
    def register(self, callback: ReminderCallback) -> None:
        """Register a callback to receive reminder events."""
        self._callbacks.append(callback)
    
    def unregister(self, callback: ReminderCallback) -> bool:
        """Unregister a callback. Returns True if found and removed."""
        try:
            self._callbacks.remove(callback)
            return True
        except ValueError:
            return False
    
    async def emit(self, event: ReminderEvent) -> None:
        """Emit event to all registered callbacks."""
        # Always call the default logging callback
        await self._default_callback.on_reminder(event)
        
        # Call registered callbacks
        for callback in self._callbacks:
            try:
                await callback.on_reminder(event)
            except Exception:
                # Log but don't let one callback failure affect others
                import logging
                logging.getLogger(__name__).exception(
                    "Error in reminder callback %s", callback.__class__.__name__
                )


# Global registry instance
reminder_registry = ReminderCallbackRegistry()


def get_reminder_registry() -> ReminderCallbackRegistry:
    """Get the global reminder callback registry."""
    return reminder_registry


def register_reminder_callback(callback: ReminderCallback) -> None:
    """Register a callback for reminder events."""
    reminder_registry.register(callback)


async def emit_reminder_event(event: ReminderEvent) -> None:
    """Emit a reminder event to all registered callbacks."""
    await reminder_registry.emit(event)