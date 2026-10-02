"""
app/api/routes/chat.py

Text-only health chat endpoint using NVIDIA Nemotron.
"""
from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm.nvidia_service import get_nvidia_service
from app.services.safety.health_safety import get_safety_validator
from app.core.config import settings

router = APIRouter(tags=["Chat"])

# Maximum message length
MAX_MESSAGE_LENGTH = 2000


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Chat with Health Assistant (Text Only)",
    description="Send a text message to the health assistant. Returns general health information.",
)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    POST /api/chat

    Text-only health chat using NVIDIA Nemotron.
    """
    # Input validation
    message = request.message.strip() if request.message else ""

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters."
        )

    # Get services
    nvidia_service = get_nvidia_service()
    safety_validator = get_safety_validator()

    try:
        # Call Nemotron
        model_response = nvidia_service.generate_response(message)

        # Safety processing
        final_response = safety_validator.process_response(message, model_response)

        # Extract disclaimer (it's always appended by safety validator)
        disclaimer = "This information is general health information and is not a diagnosis or a substitute for professional medical advice."

        return ChatResponse(
            response=final_response,
            disclaimer=disclaimer,
            model=settings.NVIDIA_MODEL,
        )

    except ValueError as e:
        # Missing API key
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please contact administrator."
        )
    except RuntimeError as e:
        # API errors, timeouts, etc.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors - don't expose internals
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )
