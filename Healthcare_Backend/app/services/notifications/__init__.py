"""
app/services/notifications/__init__.py

Notification service package exports.
"""
from app.services.notifications.models import (
    NotificationMessage,
    NotificationRecipient,
    NotificationChannel,
    NotificationType,
    NotificationResult,
)
from app.services.notifications.base import NotificationProvider
from app.services.notifications.service import NotificationService, get_notification_service, send_reminder_notification
from app.services.notifications.test_provider import TestNotificationProvider
from app.services.notifications.callback import (
    NotificationReminderCallback,
    register_notification_callback,
    unregister_notification_callback,
)

__all__ = [
    "NotificationMessage",
    "NotificationRecipient",
    "NotificationChannel",
    "NotificationType",
    "NotificationResult",
    "NotificationProvider",
    "NotificationService",
    "get_notification_service",
    "send_reminder_notification",
    "TestNotificationProvider",
    "NotificationReminderCallback",
    "register_notification_callback",
    "unregister_notification_callback",
]