"""
app/services/notifications/callback.py

Notification callback that bridges ReminderEvent to NotificationService.
"""
import logging
from typing import Optional

from app.services.events import ReminderEvent, ReminderCallback
from app.services.notifications.service import NotificationService, get_notification_service

logger = logging.getLogger(__name__)


class NotificationReminderCallback(ReminderCallback):
    """
    ReminderCallback implementation that sends notifications via NotificationService.
    
    This connects the scheduler's ReminderEvent system to the Phase 7C notification layer.
    """
    
    def __init__(self, notification_service: Optional[NotificationService] = None):
        self._notification_service = notification_service or get_notification_service()
    
    async def on_reminder(self, event: ReminderEvent) -> None:
        """
        Handle a reminder event by sending a notification.
        
        Failures are logged but never raised to avoid crashing the scheduler.
        """
        try:
            results = await self._notification_service.handle_reminder_event(event)
            
            for result in results:
                if result.success:
                    logger.info(
                        "Notification sent: %s to user=%s via %s",
                        result.notification_id,
                        result.recipient_id,
                        result.channel.value,
                    )
                else:
                    logger.warning(
                        "Notification failed: %s to user=%s via %s: %s",
                        result.notification_id,
                        result.recipient_id,
                        result.channel.value,
                        result.error_message,
                    )
        except Exception as e:
            logger.exception(
                "Unexpected error in NotificationReminderCallback for event %s",
                event.event_id,
            )


def register_notification_callback(
    notification_service: Optional[NotificationService] = None
) -> NotificationReminderCallback:
    """
    Register the notification callback with the global reminder registry.
    
    Returns the callback instance for potential unregistration.
    """
    from app.services.events import register_reminder_callback
    
    callback = NotificationReminderCallback(notification_service)
    register_reminder_callback(callback)
    logger.info("NotificationReminderCallback registered with reminder registry")
    return callback


def unregister_notification_callback(callback: NotificationReminderCallback) -> bool:
    """Unregister the notification callback."""
    from app.services.events import get_reminder_registry
    
    registry = get_reminder_registry()
    result = registry.unregister(callback)
    if result:
        logger.info("NotificationReminderCallback unregistered from reminder registry")
    return result