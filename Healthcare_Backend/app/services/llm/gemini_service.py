"""
app/services/llm/gemini_service.py

Gemini multimodal service for image and PDF processing.
Uses Google's Generative AI SDK.
"""
import os
import uuid
import shutil
from typing import Optional
from google import genai
from google.genai import types
import PIL.Image
from pypdf import PdfReader
from fastapi import HTTPException
from app.core.config import settings


# System prompt for healthcare image/PDF analysis
GEMINI_HEALTH_SYSTEM_PROMPT = (
    "You are a GENERAL HEALTH INFORMATION ASSISTANT specialized in analyzing medical images and documents.\n"
    "You may describe visible information in uploaded images, summarize content from medical documents, "
    "explain general medical terminology found in documents, or describe common health concepts.\n"
    "You must NOT diagnose diseases, claim certainty about a condition, prescribe medication, "
    "or pretend to be a doctor.\n"
    "For potentially urgent situations, encourage appropriate professional/emergency care.\n"
    "Always be helpful for general educational questions. Do not refuse normal educational questions.\n"
    "If an image or document is unclear, unreadable, or ambiguous, explicitly state that you cannot "
    "reliably determine the information.\n"
    "Never fabricate medical facts, invent values not present in the document, or cite non-existent studies."
)

# Supported file types
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}


def get_extension(filename: str) -> str:
    """Extract and return the lowercase file extension."""
    if not filename:
        return ""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def validate_file(file, max_size_mb: int = 10) -> tuple[str, str]:
    """
    Validate the uploaded file.

    Returns:
        (file_type, mime_type) where file_type is "image" or "pdf"

    Raises:
        HTTPException: If validation fails
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided or empty filename.")

    ext = get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported MIME type: {file.content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # Determine file type
    file_type = "pdf" if ext == ".pdf" else "image"
    return file_type, file.content_type


def save_upload_file(file, upload_dir: str, max_size_mb: int = 10) -> str:
    """
    Save uploaded file to a temporary location with a safe unique filename.

    Returns:
        The path to the saved file

    Raises:
        HTTPException: If file is empty, too large, or save fails
    """
    file_type, mime_type = validate_file(file, max_size_mb)

    ext = get_extension(file.filename)
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    os.makedirs(upload_dir, exist_ok=True)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        max_bytes = max_size_mb * 1024 * 1024
        if file_size > max_bytes:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {max_size_mb}MB.")

        return file_path
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        reader = PdfReader(file_path)
        if len(reader.pages) == 0:
            raise ValueError("PDF has no pages.")

        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        if not text.strip():
            raise ValueError("No text could be extracted from PDF.")

        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to process or extract text from PDF file.")


def process_image(file_path: str) -> PIL.Image.Image:
    """Load and verify an image file."""
    try:
        img = PIL.Image.open(file_path)
        img.verify()  # Verify it's a valid image
        img = PIL.Image.open(file_path)  # Reopen after verify
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to process image file. It may be corrupted or malformed.")


class GeminiMultimodalService:
    """Service for interacting with Gemini API for multimodal (image + PDF) processing."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self._client = None

    def _get_client(self):
        """Get or create the Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_response(
        self,
        user_message: str,
        file_path: Optional[str] = None,
        mime_type: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> str:
        """
        Generate a response from Gemini for multimodal health content.

        Args:
            user_message: The user's question/instruction
            file_path: Path to uploaded file (image or PDF)
            mime_type: MIME type of the file
            file_type: "image" or "pdf"

        Returns:
            The model's response text

        Raises:
            ValueError: If API key is missing
            RuntimeError: For API errors, timeouts, or empty responses
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        try:
            client = self._get_client()

            contents = []

            # Add file content if provided
            if file_path and mime_type and file_type:
                if file_type == "pdf":
                    pdf_text = extract_text_from_pdf(file_path)
                    contents.append(
                        f"--- EXTRACTED PDF TEXT ---\n{pdf_text}\n--- END PDF TEXT ---"
                    )
                elif file_type == "image":
                    img = process_image(file_path)
                    contents.append(img)

            # Add user message
            contents.append(user_message)

            config = types.GenerateContentConfig(
                system_instruction=GEMINI_HEALTH_SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=1024,
            )

            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )

            if not response.text:
                raise RuntimeError("Received empty response from Gemini API")

            return response.text.strip()

        except ValueError:
            raise
        except Exception as e:
            # Handle specific Gemini errors if possible
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
                raise RuntimeError("Gemini API authentication failed. Check your API key.")
            elif "rate limit" in error_str or "quota" in error_str:
                raise RuntimeError("Gemini API rate limit exceeded. Please try again later.")
            elif "timeout" in error_str or "timed out" in error_str:
                raise RuntimeError("Gemini API request timed out. Please try again.")
            else:
                raise RuntimeError(f"Gemini API error: {str(e)}")


# Singleton instance
_gemini_service: Optional[GeminiMultimodalService] = None


def get_gemini_service() -> GeminiMultimodalService:
    """Get the singleton GeminiMultimodalService instance."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiMultimodalService()
    return _gemini_service