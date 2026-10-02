"""
app/services/langchain/__init__.py

LangChain integration layer for healthcare backend.
"""
from app.services.langchain.adapters import NemotronAdapter
from app.services.langchain.prompts import (
    TEXT_ONLY_PROMPT,
    RAG_PROMPT,
    HEALTH_SYSTEM_PROMPT,
    URGENT_SYMPTOMS,
)
from app.services.langchain.retriever import HealthRetriever, create_health_retriever
from app.services.langchain.chains import create_text_only_chain, create_rag_chain

__all__ = [
    "NemotronAdapter",
    "TEXT_ONLY_PROMPT",
    "RAG_PROMPT",
    "HEALTH_SYSTEM_PROMPT",
    "URGENT_SYMPTOMS",
    "HealthRetriever",
    "create_health_retriever",
    "create_text_only_chain",
    "create_rag_chain",
]