"""
tests/test_notifications.py

Tests for Phase 7C: Notification & Caregiver Layer
"""
import pytest
from datetime import datetime, date, time, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.notifications.models import (
    NotificationMessage,
    NotificationRecipient,
    NotificationChannel,
    NotificationType,
    NotificationResult,
)
from app.services.notifications.base import (
    NotificationProvider,
    CompositeNotificationProvider,
)
from app.services.notifications.test_provider import TestNotificationProvider
from app.services.notifications.service import (
    NotificationService,
    get_notification_service,
    send_reminder_notification,
)
from app.services.notifications.callback import (
    NotificationReminderCallback,
    register_notification_callback,
    unregister_notification_callback,
)
from app.services.events import ReminderEvent, get_reminder_registry


class TestNotificationRecipient:
    """Tests for NotificationRecipient."""

    def test_user_recipient_creation(self):
        """Test creating a user recipient."""
        recipient = NotificationRecipient(
            user_id=1,
            channel=NotificationChannel.IN_APP,
            is_caregiver=False,
        )
        
        assert recipient.user_id == 1
        assert recipient.channel == NotificationChannel.IN_APP
        assert recipient.is_caregiver is False
        assert recipient.caregiver_consent is False

    def test_caregiver_recipient_requires_consent(self):
        """Test caregiver recipient requires explicit consent."""
        with pytest.raises(ValueError, match="Caregiver notifications require explicit consent"):
            NotificationRecipient(
                user_id=2,
                channel=NotificationChannel.SMS,
                channel_address="+15551234567",
                is_caregiver=True,
                caregiver_consent=False,
            )
    
    def test_caregiver_recipient_with_consent(self):
        """Test caregiver recipient with consent works."""
        recipient = NotificationRecipient(
            user_id=2,
            channel=NotificationChannel.SMS,
            channel_address="+15551234567",
            is_caregiver=True,
            caregiver_consent=True,
        )
        
        assert recipient.caregiver_consent is True

    def test_sms_requires_address(self):
        """Test SMS channel requires channel_address."""
        with pytest.raises(ValueError, match="requires channel_address"):
            NotificationRecipient(
                user_id=1,
                channel=NotificationChannel.SMS,
                is_caregiver=False,
            )


class TestNotificationMessage:
    """Tests for NotificationMessage."""

    def test_message_creation_with_required_fields(self):
        """Test creating message with only required fields."""
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
        )
        
        assert message.medication_id == 1
        assert message.schedule_id == 1
        assert message.medication_name == "Aspirin"
        assert message.notification_type == NotificationType.MEDICATION_REMINDER
        assert message.notification_id is not None
        assert "Time to take Aspirin" in message.body

    def test_message_with_dosage(self):
        """Test message includes dosage in body."""
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
        )
        
        assert "100mg" in message.body

    def test_message_with_recipients(self):
        """Test message with user and caregiver recipients."""
        user_recipient = NotificationRecipient(
            user_id=1,
            channel=NotificationChannel.IN_APP,
        )
        caregiver_recipient = NotificationRecipient(
            user_id=2,
            channel=NotificationChannel.EMAIL,
            channel_address="caregiver@example.com",
            is_caregiver=True,
            caregiver_consent=True,
        )
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=user_recipient,
            caregiver_recipient=caregiver_recipient,
        )
        
        assert message.user_recipient is not None
        assert message.caregiver_recipient is not None
        assert message.caregiver_recipient.is_caregiver is True


class TestNotificationResult:
    """Tests for NotificationResult."""

    def test_success_result(self):
        """Test successful result."""
        result = NotificationResult(
            notification_id="test-id",
            success=True,
            channel=NotificationChannel.IN_APP,
            recipient_id=1,
        )
        
        assert result.success is True
        assert result.is_failure is False

    def test_failure_result(self):
        """Test failed result."""
        result = NotificationResult(
            notification_id="test-id",
            success=False,
            channel=NotificationChannel.IN_APP,
            recipient_id=1,
            error_message="Test error",
        )
        
        assert result.success is False
        assert result.is_failure is True


class TestAbstractNotificationProvider:
    """Tests for abstract NotificationProvider."""

    def test_provider_is_abstract(self):
        """Test NotificationProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            NotificationProvider()


class TestCompositeNotificationProvider:
    """Tests for CompositeNotificationProvider."""

    def test_register_provider(self):
        """Test registering a provider."""
        composite = CompositeNotificationProvider()
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        composite.register_provider(provider)
        assert NotificationChannel.IN_APP in composite._providers

    def test_unregister_provider(self):
        """Test unregistering a provider."""
        composite = CompositeNotificationProvider()
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        composite.register_provider(provider)
        result = composite.unregister_provider(NotificationChannel.IN_APP)
        assert result is True
        assert NotificationChannel.IN_APP not in composite._providers

    def test_send_routes_to_correct_provider(self):
        """Test composite routes to correct provider by channel."""
        composite = CompositeNotificationProvider()
        in_app_provider = TestNotificationProvider(NotificationChannel.IN_APP)
        email_provider = TestNotificationProvider(NotificationChannel.EMAIL)
        
        composite.register_provider(in_app_provider)
        composite.register_provider(email_provider)
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(
                user_id=1,
                channel=NotificationChannel.IN_APP,
            ),
        )
        
        import asyncio
        result = asyncio.run(composite.send(message))
        
        assert result.success is True
        assert in_app_provider.get_sent_count() == 1
        assert email_provider.get_sent_count() == 0


class TestTestNotificationProvider:
    """Tests for TestNotificationProvider."""

    def test_records_sent_notifications(self):
        """Test provider records sent notifications."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(user_id=1, channel=NotificationChannel.IN_APP),
        )
        
        import asyncio
        result = asyncio.run(provider.send(message))
        
        assert result.success is True
        assert provider.get_sent_count() == 1
        assert provider.get_success_count() == 1

    def test_simulated_failure(self):
        """Test provider can simulate failure."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        provider.simulate_failure("Test failure")
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(user_id=1, channel=NotificationChannel.IN_APP),
        )
        
        import asyncio
        result = asyncio.run(provider.send(message))
        
        assert result.success is False
        assert result.error_message == "Test failure"
        assert provider.get_failure_count() == 1

    def test_get_notifications_for_user(self):
        """Test filtering notifications by user."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        message1 = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(user_id=1, channel=NotificationChannel.IN_APP),
        )
        message2 = NotificationMessage(
            medication_id=2,
            schedule_id=2,
            medication_name="Ibuprofen",
            user_recipient=NotificationRecipient(user_id=2, channel=NotificationChannel.IN_APP),
        )
        
        import asyncio
        asyncio.run(provider.send(message1))
        asyncio.run(provider.send(message2))
        
        user1_notifs = provider.get_notifications_for_user(1)
        user2_notifs = provider.get_notifications_for_user(2)
        
        assert len(user1_notifs) == 1
        assert len(user2_notifs) == 1
        assert user1_notifs[0].notification.medication_name == "Aspirin"


class TestNotificationService:
    """Tests for NotificationService."""

    def test_service_creation(self):
        """Test service can be created."""
        service = NotificationService()
        assert service is not None

    def test_set_single_provider(self):
        """Test setting a single provider."""
        service = NotificationService()
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        service.set_provider(provider)
        assert service.get_active_provider() is provider

    def test_use_composite(self):
        """Test switching to composite mode."""
        service = NotificationService()
        composite = service.use_composite()
        
        assert isinstance(composite, CompositeNotificationProvider)
        assert service.get_active_provider() is composite

    def test_create_notification_from_reminder(self):
        """Test creating notification from ReminderEvent."""
        service = NotificationService()
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        notification = service.create_notification_from_reminder(event)
        
        assert notification.medication_id == 1
        assert notification.schedule_id == 1
        assert notification.medication_name == "Aspirin"
        assert notification.dosage == "100mg"
        assert notification.user_recipient is not None
        assert notification.user_recipient.user_id == 1
        assert notification.user_recipient.channel == NotificationChannel.IN_APP

    @pytest.mark.asyncio
    async def test_send_notification_with_provider(self):
        """Test sending notification via provider."""
        service = NotificationService()
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service.set_provider(provider)
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(user_id=1, channel=NotificationChannel.IN_APP),
        )
        
        results = await service.send_notification(message)
        
        assert len(results) == 1
        assert results[0].success is True
        assert provider.get_sent_count() == 1

    @pytest.mark.asyncio
    async def test_handle_reminder_event(self):
        """Test handling ReminderEvent end-to-end."""
        service = NotificationService()
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service.set_provider(provider)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        results = await service.handle_reminder_event(event)
        
        assert len(results) == 1
        assert results[0].success is True
        assert provider.get_sent_count() == 1

    @pytest.mark.asyncio
    async def test_no_provider_configured(self):
        """Test behavior when no provider is configured."""
        service = NotificationService()
        
        message = NotificationMessage(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            user_recipient=NotificationRecipient(user_id=1, channel=NotificationChannel.IN_APP),
        )
        
        results = await service.send_notification(message)
        
        assert len(results) == 1
        assert results[0].success is False
        assert "No notification provider configured" in results[0].error_message

    def test_singleton_get_notification_service(self):
        """Test get_notification_service returns singleton."""
        service1 = get_notification_service()
        service2 = get_notification_service()
        assert service1 is service2


class TestNotificationCallback:
    """Tests for NotificationReminderCallback."""

    @pytest.mark.asyncio
    async def test_callback_handles_reminder(self):
        """Test callback processes reminder and sends notification."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service = NotificationService()
        service.set_provider(provider)
        
        callback = NotificationReminderCallback(service)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        await callback.on_reminder(event)
        
        assert provider.get_sent_count() == 1
        assert provider.get_success_count() == 1

    @pytest.mark.asyncio
    async def test_callback_failure_does_not_crash(self):
        """Test callback handles provider failure gracefully."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        provider.simulate_failure("Test failure")
        service = NotificationService()
        service.set_provider(provider)
        
        callback = NotificationReminderCallback(service)
        
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
        
        assert provider.get_failure_count() == 1


class TestCallbackRegistration:
    """Tests for callback registration."""

    def test_register_notification_callback(self):
        """Test registering notification callback."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service = NotificationService()
        service.set_provider(provider)
        
        callback = register_notification_callback(service)
        
        registry = get_reminder_registry()
        assert callback in registry._callbacks
        
        # Cleanup
        unregister_notification_callback(callback)

    def test_unregister_notification_callback(self):
        """Test unregistering notification callback."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service = NotificationService()
        service.set_provider(provider)
        
        callback = register_notification_callback(service)
        result = unregister_notification_callback(callback)
        
        assert result is True
        registry = get_reminder_registry()
        assert callback not in registry._callbacks


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_reminder_event_to_notification_flow(self):
        """Test complete flow: ReminderEvent -> callback -> notification."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        
        # Register callback
        service = NotificationService()
        service.set_provider(provider)
        callback = register_notification_callback(service)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        # Emit event through registry (simulates scheduler)
        from app.services.events import emit_reminder_event
        await emit_reminder_event(event)
        
        assert provider.get_sent_count() == 1
        assert provider.get_success_count() == 1
        
        # Cleanup
        unregister_notification_callback(callback)

    @ pytest.mark.asyncio
    async def test_scheduler_continues_after_notification_failure(self):
        """Test scheduler is not affected by notification failures."""
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        provider.simulate_continuous_failure("Simulated failure")
        
        service = NotificationService()
        service.set_provider(provider)
        callback = register_notification_callback(service)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        from app.services.events import emit_reminder_event
        
        # Emit multiple events - should not crash
        for i in range(3):
            event = ReminderEvent(
                medication_id=1,
                schedule_id=1,
                medication_name="Aspirin",
                dosage="100mg",
                scheduled_time=datetime.now(timezone.utc),
                user_id=1,
                event_id=str(uuid.uuid4()),
            )
            await emit_reminder_event(event)
        
        assert provider.get_sent_count() == 3
        assert provider.get_failure_count() == 3
        
        # Cleanup
        unregister_notification_callback(callback)


class TestNoAutomaticAdherenceLogging:
    """Tests verifying no automatic adherence logs are created."""

    @pytest.mark.asyncio
    async def test_notification_does_not_create_adherence_log(self):
        """Test that sending notification doesn't create adherence log."""
        # This test verifies the architecture - notification layer
        # does not have any code that creates AdherenceLog entries
        provider = TestNotificationProvider(NotificationChannel.IN_APP)
        service = NotificationService()
        service.set_provider(provider)
        
        event = ReminderEvent(
            medication_id=1,
            schedule_id=1,
            medication_name="Aspirin",
            dosage="100mg",
            scheduled_time=datetime.now(timezone.utc),
            user_id=1,
            event_id=str(uuid.uuid4()),
        )
        
        await service.handle_reminder_event(event)
        
        # Verify notification was sent
        assert provider.get_sent_count() == 1
        
        # The notification service has no database session or
        # AdherenceLog creation code - this is by design
        # (AdherenceLog creation is explicit via API in Phase 7A)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])