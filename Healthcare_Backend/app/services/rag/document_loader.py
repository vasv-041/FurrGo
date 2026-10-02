"""
app/services/rag/document_loader.py
"""
from pypdf import PdfReader
from fastapi import HTTPException

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
                text += extracted + "\n\n"
        if not text.strip():
            raise ValueError("No text could be extracted from PDF.")
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to process or extract text from PDF file.")
