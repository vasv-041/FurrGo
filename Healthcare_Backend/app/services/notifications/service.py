"""
app/services/notifications/service.py

Notification service for Phase 7C.
Connects ReminderEvent to notification providers.
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone

from app.services.events import ReminderEvent
from app.services.notifications.base import NotificationProvider, CompositeNotificationProvider
from app.services.notifications.models import (
    NotificationMessage,
    NotificationRecipient,
    NotificationChannel,
    NotificationType,
    NotificationResult,
)
from app.services.notifications.test_provider import TestNotificationProvider

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for creating and delivering notifications.
    
    Consumes ReminderEvent from scheduler and delivers via registered providers.
    """
    
    def __init__(self):
        self._provider: Optional[NotificationProvider] = None
        self._composite_provider: Optional[CompositeNotificationProvider] = None
        self._use_composite: bool = False
    
    def set_provider(self, provider: NotificationProvider) -> None:
        """Set a single provider for all channels."""
        self._provider = provider
        self._composite_provider = None
        self._use_composite = False
    
    def use_composite(self) -> CompositeNotificationProvider:
        """Switch to composite provider mode."""
        if self._composite_provider is None:
            self._composite_provider = CompositeNotificationProvider()
        self._use_composite = True
        self._provider = None
        return self._composite_provider
    
    def get_active_provider(self) -> Optional[NotificationProvider]:
        """Get the currently active provider."""
        if self._use_composite:
            return self._composite_provider
        return self._provider
    
    def create_notification_from_reminder(self, event: ReminderEvent) -> NotificationMessage:
        """
        Create a NotificationMessage from a ReminderEvent.
        
        This is the main integration point between scheduler and notifications.
        """
        # Create user recipient (default to in_app channel)
        user_recipient = NotificationRecipient(
            user_id=event.user_id,
            channel=NotificationChannel.IN_APP,
            is_caregiver=False,
        )
        
        message = NotificationMessage(
            medication_id=event.medication_id,
            schedule_id=event.schedule_id,
            medication_name=event.medication_name,
            dosage=event.dosage,
            scheduled_time=event.scheduled_time,
            notification_type=NotificationType.MEDICATION_REMINDER,
            user_recipient=user_recipient,
        )
        
        return message
    
    async def send_notification(self, notification: NotificationMessage) -> List[NotificationResult]:
        """
        Send a notification via the active provider.
        
        Returns list of results (one per recipient).
        """
        provider = self.get_active_provider()
        
        if provider is None:
            logger.warning("No notification provider configured, skipping send")
            return [NotificationResult(
                notification_id=notification.notification_id,
                success=False,
                channel=NotificationChannel.IN_APP,
                recipient_id=notification.user_recipient.user_id if notification.user_recipient else 0,
                error_message="No notification provider configured"
            )]
        
        results = []
        
        # Send to user recipient
        if notification.user_recipient:
            try:
                if self._use_composite and isinstance(provider, CompositeNotificationProvider):
                    # Composite handles routing internally
                    result = await provider.send(notification)
                    results.append(result)
                else:
                    # Single provider
                    result = await provider.send_to_user(notification, notification.user_recipient.user_id)
                    results.append(result)
            except Exception as e:
                logger.exception("Failed to send user notification")
                results.append(NotificationResult(
                    notification_id=notification.notification_id,
                    success=False,
                    channel=notification.user_recipient.channel,
                    recipient_id=notification.user_recipient.user_id,
                    error_message=str(e),
                ))
        
        # Send to caregiver recipient (if present and consented)
        if notification.caregiver_recipient and notification.caregiver_recipient.caregiver_consent:
            try:
                if self._use_composite and isinstance(provider, CompositeNotificationProvider):
                    # Already handled by composite's send()
                    pass
                else:
                    result = await provider.send_to_caregiver(notification, notification.caregiver_recipient.user_id)
                    results.append(result)
            except Exception as e:
                logger.exception("Failed to send caregiver notification")
                results.append(NotificationResult(
                    notification_id=notification.notification_id,
                    success=False,
                    channel=notification.caregiver_recipient.channel,
                    recipient_id=notification.caregiver_recipient.user_id,
                    error_message=str(e),
                ))
        
        return results
    
    async def handle_reminder_event(self, event: ReminderEvent) -> List[NotificationResult]:
        """
        Handle a ReminderEvent from the scheduler.
        
        Creates notification and sends via provider.
        Never raises - failures are logged and returned in results.
        """
        notification = self.create_notification_from_reminder(event)
        return await self.send_notification(notification)


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# Convenience function for direct event handling
async def send_reminder_notification(event: ReminderEvent) -> List[NotificationResult]:
    """
    Send a reminder notification.
    
    This is the main entry point for the ReminderCallback integration.
    """
    service = get_notification_service()
    return await service.handle_reminder_event(event)