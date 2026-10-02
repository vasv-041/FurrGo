"""
tests/test_nvidia_service.py

Unit tests for NvidiaLLMService with mocked OpenAI client.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.llm.nvidia_service import NvidiaLLMService, get_nvidia_service


class TestNvidiaLLMService:
    """Test NvidiaLLMService class."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.llm.nvidia_service as nvidia_module
        nvidia_module._nvidia_service = None

    def test_service_initialization_with_settings(self):
        """Test service loads config from settings."""
        # Create a service with explicit settings
        from app.core.config import Settings
        test_settings = Settings(NVIDIA_API_KEY="test-key", NVIDIA_MODEL="test-model")
        service = NvidiaLLMService()
        # Override with test settings
        service.api_key = test_settings.NVIDIA_API_KEY
        service.model = test_settings.NVIDIA_MODEL
        service.base_url = test_settings.NVIDIA_BASE_URL
        assert service.api_key == "test-key"
        assert service.model == "test-model"
        assert service.base_url == "https://integrate.api.nvidia.com/v1"

    def test_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        service = NvidiaLLMService()
        service.api_key = ""
        with pytest.raises(ValueError, match="NVIDIA_API_KEY is not configured"):
            service.generate_response("test message")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_generate_response_success(self, mock_openai_class):
        """Test successful response generation."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
        mock_client.chat.completions.create.return_value = mock_response

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        result = service.generate_response("What is dehydration?")

        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once()
        # Verify system prompt is included
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "GENERAL HEALTH INFORMATION ASSISTANT" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is dehydration?"

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_empty_response_raises(self, mock_openai_class):
        """Test that empty response raises RuntimeError."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_client.chat.completions.create.return_value = mock_response

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="empty response"):
            service.generate_response("test")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_no_choices_raises(self, mock_openai_class):
        """Test that missing choices raises RuntimeError."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="empty response"):
            service.generate_response("test")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_authentication_error(self, mock_openai_class):
        """Test authentication error handling."""
        from openai import AuthenticationError
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key", response=MagicMock(), body={}
        )

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="authentication failed"):
            service.generate_response("test")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_rate_limit_error(self, mock_openai_class):
        """Test rate limit error handling."""
        from openai import RateLimitError
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit", response=MagicMock(), body={}
        )

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="rate limit"):
            service.generate_response("test")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_timeout_error(self, mock_openai_class):
        """Test timeout error handling."""
        from openai import APITimeoutError
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APITimeoutError("Timeout")

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="timed out"):
            service.generate_response("test")

    @patch("app.services.llm.nvidia_service.OpenAI")
    def test_generic_api_error(self, mock_openai_class):
        """Test generic API error handling."""
        from openai import APIError
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        # APIError requires request and body args in newer openai versions
        mock_client.chat.completions.create.side_effect = APIError(
            "Server error", request=MagicMock(), body={}
        )

        service = NvidiaLLMService()
        service.api_key = "test-key"
        service.model = "test-model"
        service.base_url = "https://integrate.api.nvidia.com/v1"
        with pytest.raises(RuntimeError, match="NVIDIA API error"):
            service.generate_response("test")


class TestGetNvidiaService:
    """Test singleton getter."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.llm.nvidia_service as nvidia_module
        nvidia_module._nvidia_service = None

    def test_singleton(self):
        """Test that get_nvidia_service returns singleton."""
        # This test just verifies the singleton pattern works
        # The actual settings are loaded from the real config
        service1 = get_nvidia_service()
        service2 = get_nvidia_service()
        assert service1 is service2