"""
app/services/file_service.py

Handles saving and validating uploaded files.
"""
import os
import uuid
import shutil
from fastapi import UploadFile, HTTPException
from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}

def get_extension(filename: str) -> str:
    if not filename:
        return ""
    _, ext = os.path.splitext(filename)
    return ext.lower()

def validate_file(file: UploadFile):
    """Validates the uploaded file."""
    if not file:
        return
        
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename provided.")

    ext = get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported MIME type.")

def save_upload_file(file: UploadFile) -> str:
    """Saves the uploaded file to the configured upload directory with a safe unique filename."""
    validate_file(file)
    
    upload_dir = os.path.join(settings.UPLOAD_DIR, "chat")
    os.makedirs(upload_dir, exist_ok=True)
    
    ext = get_extension(file.filename)
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Check size limit
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB.")
            
        return file_path
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")
