"""
app/api/routes/chat.py

Health chat endpoint supporting text, image, and PDF inputs.
Routes to NVIDIA Nemotron for text-only, Gemini for multimodal.
"""
import os
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm.nvidia_service import get_nvidia_service
from app.services.llm.gemini_service import get_gemini_service, save_upload_file, get_extension
from app.services.safety.health_safety import get_safety_validator
from app.core.config import settings

router = APIRouter(tags=["Chat"])

# Maximum message length
MAX_MESSAGE_LENGTH = 2000
# Maximum upload size (can be overridden by settings)
MAX_UPLOAD_SIZE_MB = 10


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Chat with Health Assistant",
    description="Send a text message with an optional image (PNG/JPG/JPEG) or PDF file to the health assistant.",
)
async def chat_endpoint(
    message: str = Form(...),
    file: Optional[UploadFile] = File(None)
) -> ChatResponse:
    """
    POST /api/chat

    Multimodal health chat:
    - Text only → NVIDIA Nemotron
    - Text + Image/PDF → Google Gemini
    """
    # Input validation for message
    message = message.strip() if message else ""

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
    safety_validator = get_safety_validator()
    file_path = None
    file_processed = False
    file_type_str = None
    mime_type = None

    try:
        if file and file.filename:
            # Save and validate uploaded file
            upload_dir = os.path.join(settings.UPLOAD_DIR, "chat")
            file_path = save_upload_file(file, upload_dir, MAX_UPLOAD_SIZE_MB)
            mime_type = file.content_type
            file_processed = True

            ext = get_extension(file.filename)
            if ext == ".pdf":
                file_type_str = "pdf"
            elif ext in [".png", ".jpg", ".jpeg"]:
                file_type_str = "image"

            # Route to Gemini for multimodal
            gemini_service = get_gemini_service()
            model_response = gemini_service.generate_response(
                user_message=message,
                file_path=file_path,
                mime_type=mime_type,
                file_type=file_type_str
            )
            model_used = settings.GEMINI_MODEL
        else:
            # Text only → Nemotron
            nvidia_service = get_nvidia_service()
            model_response = nvidia_service.generate_response(message)
            model_used = settings.NVIDIA_MODEL

        # Safety processing
        final_response = safety_validator.process_response(message, model_response)

        # Extract disclaimer (always appended by safety validator)
        disclaimer = "This information is general health information and is not a diagnosis or a substitute for professional medical advice."

        return ChatResponse(
            response=final_response,
            disclaimer=disclaimer,
            model=model_used,
            file_processed=file_processed,
            file_type=file_type_str
        )

    except HTTPException:
        raise
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
    finally:
        # Clean up uploaded file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
