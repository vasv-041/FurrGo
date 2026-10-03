"""
app/services/notifications/base.py

Abstract notification provider interface for Phase 7C.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.services.notifications.models import (
    NotificationMessage,
    NotificationResult,
    NotificationChannel,
)


class NotificationProvider(ABC):
    """
    Abstract base class for notification providers.
    
    Implement this to provide actual notification delivery.
    The provider must be replaceable - test with test provider,
    swap for production provider (Twilio, FCM, etc.) later.
    """
    
    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """The notification channel this provider handles."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        pass
    
    @abstractmethod
    async def send(self, notification: NotificationMessage) -> NotificationResult:
        """
        Send a notification.
        
        Args:
            notification: The notification to send
            
        Returns:
            NotificationResult with success status and metadata
            
        Should never raise - return failure result instead.
        """
        pass
    
    async def send_to_user(
        self,
        notification: NotificationMessage,
        recipient_user_id: int
    ) -> NotificationResult:
        """
        Send notification to a specific user.
        
        Override if provider needs user-specific logic.
        Default: extracts user_recipient from notification.
        """
        if notification.user_recipient and notification.user_recipient.user_id == recipient_user_id:
            return await self.send(notification)
        
        return NotificationResult(
            notification_id=notification.notification_id,
            success=False,
            channel=self.channel,
            recipient_id=recipient_user_id,
            error_message="No matching user recipient in notification"
        )
    
    async def send_to_caregiver(
        self,
        notification: NotificationMessage,
        recipient_user_id: int
    ) -> NotificationResult:
        """
        Send notification to a caregiver.
        
        Override if provider needs caregiver-specific logic.
        Default: extracts caregiver_recipient from notification.
        """
        if (notification.caregiver_recipient 
            and notification.caregiver_recipient.user_id == recipient_user_id
            and notification.caregiver_recipient.caregiver_consent):
            return await self.send(notification)
        
        return NotificationResult(
            notification_id=notification.notification_id,
            success=False,
            channel=self.channel,
            recipient_id=recipient_user_id,
            error_message="No matching caregiver recipient or missing consent"
        )


class CompositeNotificationProvider(NotificationProvider):
    """
    Provider that delegates to multiple providers based on channel.
    
    Allows registering multiple providers for different channels.
    """
    
    def __init__(self):
        self._providers: dict[NotificationChannel, NotificationProvider] = {}
    
    @property
    def channel(self) -> NotificationChannel:
        raise NotImplementedError("Composite provider has no single channel")
    
    @property
    def name(self) -> str:
        return "composite"
    
    def register_provider(self, provider: NotificationProvider) -> None:
        """Register a provider for its channel."""
        self._providers[provider.channel] = provider
    
    def unregister_provider(self, channel: NotificationChannel) -> bool:
        """Unregister a provider for a channel."""
        if channel in self._providers:
            del self._providers[channel]
            return True
        return False
    
    async def send(self, notification: NotificationMessage) -> NotificationResult:
        """
        Route notification to appropriate provider based on recipient channels.
        
        Sends to both user and caregiver recipients if present.
        Returns first failure or combined result.
        """
        results = []
        
        # Send to user recipient
        if notification.user_recipient:
            provider = self._providers.get(notification.user_recipient.channel)
            if provider:
                result = await provider.send_to_user(
                    notification, notification.user_recipient.user_id
                )
                results.append(result)
            else:
                results.append(NotificationResult(
                    notification_id=notification.notification_id,
                    success=False,
                    channel=notification.user_recipient.channel,
                    recipient_id=notification.user_recipient.user_id,
                    error_message=f"No provider for channel {notification.user_recipient.channel}"
                ))
        
        # Send to caregiver recipient
        if notification.caregiver_recipient and notification.caregiver_recipient.caregiver_consent:
            provider = self._providers.get(notification.caregiver_recipient.channel)
            if provider:
                result = await provider.send_to_caregiver(
                    notification, notification.caregiver_recipient.user_id
                )
                results.append(result)
            else:
                results.append(NotificationResult(
                    notification_id=notification.notification_id,
                    success=False,
                    channel=notification.caregiver_recipient.channel,
                    recipient_id=notification.caregiver_recipient.user_id,
                    error_message=f"No provider for channel {notification.caregiver_recipient.channel}"
                ))
        
        if not results:
            return NotificationResult(
                notification_id=notification.notification_id,
                success=False,
                channel=NotificationChannel.IN_APP,
                recipient_id=0,
                error_message="No recipients to notify"
            )
        
        # Return first failure, or success if all succeeded
        for result in results:
            if not result.success:
                return result
        return results[0]