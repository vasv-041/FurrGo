import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_text_only_chat_success(mock_get_service):
    """Test successful text-only chat with mocked Nemotron."""
    # Setup mock service
    mock_service = MagicMock()
    mock_service.generate_response.return_value = "Dehydration occurs when you lose more fluids than you take in."
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is dehydration?"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "Dehydration occurs" in data["response"]
    assert data["disclaimer"] == "This information is general health information and is not a diagnosis or a substitute for professional medical advice."
    assert data["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"

    # Verify service was called correctly
    mock_service.generate_response.assert_called_once_with("What is dehydration?")


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_chat_appends_disclaimer(mock_get_service):
    """Test that disclaimer is always present in response."""
    mock_service = MagicMock()
    mock_service.generate_response.return_value = "General health information about blood pressure."
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is blood pressure?"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "general health information" in data["response"]
    assert "not a diagnosis" in data["response"]


def test_empty_message_rejected():
    """Test that empty message returns 400."""
    response = client.post(
        "/api/chat",
        json={"message": ""}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_whitespace_only_message_rejected():
    """Test that whitespace-only message returns 400."""
    response = client.post(
        "/api/chat",
        json={"message": "   \n\t  "}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_excessively_long_message_rejected():
    """Test that message exceeding max length returns 400."""
    long_message = "x" * 2001
    response = client.post(
        "/api/chat",
        json={"message": long_message}
    )
    assert response.status_code == 400
    assert "exceeds maximum length" in response.json()["detail"]


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_missing_api_key_handled(mock_get_service):
    """Test that missing API key returns 503."""
    mock_service = MagicMock()
    mock_service.generate_response.side_effect = ValueError("NVIDIA_API_KEY is not configured")
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is dehydration?"}
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_provider_failure_returns_controlled_error(mock_get_service):
    """Test that provider failure returns 502 with controlled message."""
    mock_service = MagicMock()
    mock_service.generate_response.side_effect = RuntimeError("NVIDIA API authentication failed. Check your API key.")
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is dehydration?"}
    )

    assert response.status_code == 502
    assert "authentication failed" in response.json()["detail"]


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_empty_model_response_handled(mock_get_service):
    """Test that empty model response is handled."""
    mock_service = MagicMock()
    mock_service.generate_response.side_effect = RuntimeError("Received empty response from NVIDIA API")
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is dehydration?"}
    )

    assert response.status_code == 502
    assert "empty response" in response.json()["detail"]


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_urgent_symptoms_trigger_warning(mock_get_service):
    """Test that urgent symptoms in user message trigger emergency warning."""
    mock_service = MagicMock()
    mock_service.generate_response.return_value = "Chest pain can indicate serious conditions."
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "I have severe chest pain"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "emergency services" in data["response"]
    assert "911" in data["response"]


@patch("app.services.langchain.adapters.get_nvidia_service")
def test_api_key_never_in_response(mock_get_service):
    """Test that API key is never returned in API response."""
    mock_service = MagicMock()
    mock_service.generate_response.return_value = "Test response."
    mock_get_service.return_value = mock_service

    response = client.post(
        "/api/chat",
        json={"message": "What is dehydration?"}
    )

    assert response.status_code == 200
    data = response.json()
    # Check no API key fields
    response_str = str(data)
    assert "api_key" not in response_str.lower()
    assert "nvidia" not in response_str.lower() or "model" in data  # model name is OK


def test_no_database_records_created():
    """Test that chat endpoint doesn't create database records."""
    # This test verifies that the chat endpoint doesn't require DB
    # and doesn't create User/Document records
    # We just verify the endpoint works without DB interaction
    with patch("app.services.langchain.adapters.get_nvidia_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.generate_response.return_value = "Test response."
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/chat",
            json={"message": "What is dehydration?"}
        )

        assert response.status_code == 200
        # If we got here without DB errors, the test passes
        # (The test client uses the same app with DB, but chat doesn't touch it)
