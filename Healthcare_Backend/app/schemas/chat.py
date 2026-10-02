"""
app/schemas/chat.py
"""
from pydantic import BaseModel
from typing import Optional, List


class SourceMetadata(BaseModel):
    document_id: int
    page_number: int
    chunk_index: int


class ChatRequest(BaseModel):
    message: str
    document_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    disclaimer: str
    model: str
    sources: List[dict] = []
