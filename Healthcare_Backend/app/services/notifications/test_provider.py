"""
app/services/notifications/test_provider.py

Test-safe notification provider for Phase 7C testing.
"""
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.notifications.base import NotificationProvider
from app.services.notifications.models import (
    NotificationMessage,
    NotificationResult,
    NotificationChannel,
)

logger = logging.getLogger(__name__)


@dataclass
class SentNotification:
    """Record of a sent notification for test verification."""
    notification: NotificationMessage
    result: NotificationResult
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TestNotificationProvider(NotificationProvider):
    """
    Test notification provider that records notifications instead of sending.
    
    Use this in tests to verify notification behavior without external calls.
    """
    
    def __init__(self, channel: NotificationChannel = NotificationChannel.IN_APP, name: str = "test"):
        self._channel = channel
        self._name = name
        self.sent_notifications: List[SentNotification] = []
        self._fail_next: bool = False
        self._fail_always: bool = False
        self._fail_message: str = "Simulated test failure"
    
    @property
    def channel(self) -> NotificationChannel:
        return self._channel
    
    @property
    def name(self) -> str:
        return self._name
    
    async def send(self, notification: NotificationMessage) -> NotificationResult:
        """Record the notification and return success (or simulated failure)."""
        should_fail = self._fail_always or self._fail_next
        if self._fail_next:
            self._fail_next = False
        
        if should_fail:
            result = NotificationResult(
                notification_id=notification.notification_id,
                success=False,
                channel=self._channel,
                recipient_id=notification.user_recipient.user_id if notification.user_recipient else 0,
                error_message=self._fail_message,
            )
        else:
            result = NotificationResult(
                notification_id=notification.notification_id,
                success=True,
                channel=self._channel,
                recipient_id=notification.user_recipient.user_id if notification.user_recipient else 0,
                provider_response={"test": True, "provider": self._name},
            )
        
        self.sent_notifications.append(SentNotification(
            notification=notification,
            result=result,
        ))
        
        logger.info(
            "Test notification %s: %s (channel=%s, recipient=%s)",
            "failed" if not result.success else "sent",
            notification.notification_id,
            self._channel,
            notification.user_recipient.user_id if notification.user_recipient else "none",
        )
        
        return result
    
    def simulate_failure(self, message: str = "Simulated test failure") -> None:
        """Configure the next send to fail."""
        self._fail_next = True
        self._fail_message = message
    
    def simulate_continuous_failure(self, message: str = "Simulated test failure") -> None:
        """Configure all subsequent sends to fail."""
        self._fail_always = True
        self._fail_message = message
    
    def get_sent_count(self) -> int:
        """Get total notifications sent."""
        return len(self.sent_notifications)
    
    def get_success_count(self) -> int:
        """Get successful notifications sent."""
        return sum(1 for n in self.sent_notifications if n.result.success)
    
    def get_failure_count(self) -> int:
        """Get failed notifications sent."""
        return sum(1 for n in self.sent_notifications if not n.result.success)
    
    def clear(self) -> None:
        """Clear sent notifications history."""
        self.sent_notifications.clear()
    
    def get_last_notification(self) -> Optional[SentNotification]:
        """Get the most recent notification."""
        return self.sent_notifications[-1] if self.sent_notifications else None
    
    def get_notifications_for_user(self, user_id: int) -> List[SentNotification]:
        """Get all notifications sent to a specific user."""
        return [
            n for n in self.sent_notifications
            if n.notification.user_recipient and n.notification.user_recipient.user_id == user_id
        ]