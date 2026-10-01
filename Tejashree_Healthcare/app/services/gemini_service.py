"""
app/services/gemini_service.py

Handles interaction with the Gemini API.
"""
import os
from google import genai
from google.genai import types
import PIL.Image
from pypdf import PdfReader
from fastapi import HTTPException
from app.core.config import settings

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a PDF file using pypdf."""
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

def get_gemini_response(message: str, file_path: str = None, mime_type: str = None) -> str:
    """Sends message and optional file content to Gemini API."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key is missing.")

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        system_instruction = (
            "You are a GENERAL HEALTH INFORMATION ASSISTANT.\n"
            "You may explain general health concepts, medical terminology, summarize information from an uploaded report, "
            "or describe visible information in an uploaded image.\n"
            "You must NOT diagnose diseases, claim certainty about a condition, prescribe medication, or pretend to be a doctor.\n"
            "For potentially urgent situations, encourage appropriate professional/emergency care.\n"
            "Always be helpful for general educational questions like 'What is blood pressure?'. Do not refuse normal educational questions."
        )
        
        contents = []
        
        if file_path and mime_type:
            if mime_type == "application/pdf":
                pdf_text = extract_text_from_pdf(file_path)
                contents.append(f"--- EXTRACTED PDF TEXT ---\n{pdf_text}\n--- END PDF TEXT ---")
            elif mime_type in ["image/jpeg", "image/png"]:
                try:
                    img = PIL.Image.open(file_path)
                    img.verify()
                    img = PIL.Image.open(file_path) 
                    contents.append(img)
                except Exception as e:
                    raise HTTPException(status_code=400, detail="Failed to process image file. It may be corrupted or malformed.")
        
        contents.append(message)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction
        )
        
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=config
        )
        
        if not response.text:
            raise ValueError("Received empty response from Gemini.")
            
        return response.text

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail="External AI provider error.")
