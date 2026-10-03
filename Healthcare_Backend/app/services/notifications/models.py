"""
app/services/notifications/models.py

Structured notification models for Phase 7C.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
import uuid


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    IN_APP = "in_app"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    PUSH = "push"


class NotificationType(str, Enum):
    """Types of notifications."""
    MEDICATION_REMINDER = "medication_reminder"
    CAREGIVER_ALERT = "caregiver_alert"
    ADHERENCE_SUMMARY = "adherence_summary"
    SYSTEM = "system"


@dataclass(frozen=True)
class NotificationRecipient:
    """Recipient of a notification."""
    user_id: int
    channel: NotificationChannel
    channel_address: Optional[str] = None  # e.g., phone number, email, push token
    is_caregiver: bool = False
    caregiver_consent: bool = False  # Must be True for caregiver notifications

    def __post_init__(self):
        if self.is_caregiver and not self.caregiver_consent:
            raise ValueError("Caregiver notifications require explicit consent")
        if self.channel in (NotificationChannel.WHATSAPP, NotificationChannel.SMS) and not self.channel_address:
            raise ValueError(f"Channel {self.channel} requires channel_address")


@dataclass(frozen=True)
class NotificationMessage:
    """
    Structured notification message.
    
    Contains only information needed for safe notification delivery.
    No diagnosis or sensitive health information.
    """
    # Required fields (no defaults)
    medication_id: int
    schedule_id: int
    medication_name: str
    
    # Optional fields with defaults
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_type: NotificationType = NotificationType.MEDICATION_REMINDER
    dosage: Optional[str] = None
    scheduled_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Recipients
    user_recipient: Optional[NotificationRecipient] = None
    caregiver_recipient: Optional[NotificationRecipient] = None
    
    # Content
    title: str = "Medication Reminder"
    body: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.body == "":
            dosage_str = f" ({self.dosage})" if self.dosage else ""
            object.__setattr__(
                self,
                "body",
                f"Time to take {self.medication_name}{dosage_str}"
            )


@dataclass(frozen=True)
class NotificationResult:
    """Result of a notification send attempt."""
    notification_id: str
    success: bool
    channel: NotificationChannel
    recipient_id: int
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None

    @property
    def is_failure(self) -> bool:
        return not self.success