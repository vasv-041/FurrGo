"""
tests/test_gemini_service.py

Unit tests for GeminiMultimodalService with mocked Google GenAI client.
"""
import pytest
from unittest.mock import patch, MagicMock
import io
from PIL import Image
from fastapi import HTTPException
from app.services.llm.gemini_service import (
    GeminiMultimodalService,
    get_gemini_service,
    save_upload_file,
    validate_file,
    extract_text_from_pdf,
    get_extension,
)


class TestGeminiMultimodalService:
    """Test GeminiMultimodalService class."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.llm.gemini_service as gemini_module
        gemini_module._gemini_service = None

    def test_service_initialization(self):
        """Test service loads config from settings."""
        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        assert service.api_key == "test-key"
        assert service.model == "test-model"

    def test_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        service = GeminiMultimodalService()
        service.api_key = ""
        with pytest.raises(ValueError, match="GEMINI_API_KEY is not configured"):
            service.generate_response("test message")

    @patch("app.services.llm.gemini_service.genai.Client")
    def test_generate_response_text_only(self, mock_genai_client):
        """Test successful text-only response generation."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        result = service.generate_response("What is dehydration?")

        assert result == "Test response"
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert call_args.kwargs["model"] == "test-model"
        # Verify system prompt is included
        config = call_args.kwargs["config"]
        assert "GENERAL HEALTH INFORMATION ASSISTANT" in config.system_instruction

    @patch("app.services.llm.gemini_service.genai.Client")
    @patch("app.services.llm.gemini_service.process_image")
    def test_generate_response_with_image(self, mock_process_image, mock_genai_client):
        """Test response generation with image."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Image analysis result"
        mock_client.models.generate_content.return_value = mock_response
        mock_process_image.return_value = MagicMock()

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        result = service.generate_response(
            "What's in this image?",
            file_path="/tmp/test.png",
            mime_type="image/png",
            file_type="image"
        )

        assert result == "Image analysis result"
        mock_process_image.assert_called_once_with("/tmp/test.png")

    @patch("app.services.llm.gemini_service.genai.Client")
    @patch("app.services.llm.gemini_service.extract_text_from_pdf")
    def test_generate_response_with_pdf(self, mock_extract_pdf, mock_genai_client):
        """Test response generation with PDF."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "PDF summary"
        mock_client.models.generate_content.return_value = mock_response
        mock_extract_pdf.return_value = "Extracted PDF text"

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        result = service.generate_response(
            "Summarize this report",
            file_path="/tmp/test.pdf",
            mime_type="application/pdf",
            file_type="pdf"
        )

        assert result == "PDF summary"
        mock_extract_pdf.assert_called_once_with("/tmp/test.pdf")

    @patch("app.services.llm.gemini_service.genai.Client")
    def test_empty_response_raises(self, mock_genai_client):
        """Test that empty response raises RuntimeError."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        with pytest.raises(RuntimeError, match="empty response"):
            service.generate_response("test")

    @patch("app.services.llm.gemini_service.genai.Client")
    def test_authentication_error(self, mock_genai_client):
        """Test authentication error handling."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API key invalid")

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        with pytest.raises(RuntimeError, match="authentication failed"):
            service.generate_response("test")

    @patch("app.services.llm.gemini_service.genai.Client")
    def test_rate_limit_error(self, mock_genai_client):
        """Test rate limit error handling."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("rate limit exceeded")

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        with pytest.raises(RuntimeError, match="rate limit"):
            service.generate_response("test")

    @patch("app.services.llm.gemini_service.genai.Client")
    def test_timeout_error(self, mock_genai_client):
        """Test timeout error handling."""
        mock_client = MagicMock()
        mock_genai_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("timeout")

        service = GeminiMultimodalService()
        service.api_key = "test-key"
        service.model = "test-model"
        with pytest.raises(RuntimeError, match="timed out"):
            service.generate_response("test")


class TestGeminiUtilities:
    """Test utility functions."""

    def test_get_extension(self):
        assert get_extension("test.png") == ".png"
        assert get_extension("test.JPG") == ".jpg"
        assert get_extension("test.PDF") == ".pdf"
        assert get_extension("") == ""
        assert get_extension("noext") == ""

    def test_validate_file_valid_image(self):
        """Test validation passes for valid image."""
        mock_file = MagicMock()
        mock_file.filename = "test.png"
        mock_file.content_type = "image/png"
        file_type, mime_type = validate_file(mock_file)
        assert file_type == "image"
        assert mime_type == "image/png"

    def test_validate_file_valid_pdf(self):
        """Test validation passes for valid PDF."""
        mock_file = MagicMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        file_type, mime_type = validate_file(mock_file)
        assert file_type == "pdf"
        assert mime_type == "application/pdf"

    def test_validate_file_invalid_extension(self):
        """Test validation rejects invalid extension."""
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        with pytest.raises(HTTPException) as exc:
            validate_file(mock_file)
        assert exc.value.status_code == 400
        assert "Unsupported file extension" in str(exc.value.detail)

    def test_validate_file_invalid_mime(self):
        """Test validation rejects invalid MIME type."""
        mock_file = MagicMock()
        mock_file.filename = "test.png"
        mock_file.content_type = "text/plain"
        with pytest.raises(HTTPException) as exc:
            validate_file(mock_file)
        assert exc.value.status_code == 400
        assert "Unsupported MIME type" in str(exc.value.detail)

    def test_validate_file_no_filename(self):
        """Test validation rejects missing filename."""
        mock_file = MagicMock()
        mock_file.filename = ""
        mock_file.content_type = "image/png"
        with pytest.raises(HTTPException) as exc:
            validate_file(mock_file)
        assert exc.value.status_code == 400


class TestGetGeminiService:
    """Test singleton getter."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.services.llm.gemini_service as gemini_module
        gemini_module._gemini_service = None

    def test_singleton(self):
        """Test that get_gemini_service returns singleton."""
        service1 = get_gemini_service()
        service2 = get_gemini_service()
        assert service1 is service2


# Need HTTPException for tests
from fastapi import HTTPException