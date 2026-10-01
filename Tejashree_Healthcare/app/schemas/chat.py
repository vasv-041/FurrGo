"""
app/schemas/chat.py
"""
from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    disclaimer: str
    model: str
