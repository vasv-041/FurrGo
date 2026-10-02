"""
app/services/rag/embeddings.py

Embedding service for generating vector embeddings from text.
Supports configurable providers (sentence_transformers, openai, etc.).
"""

import os
from typing import List, Optional
from app.core.config import settings


class EmbeddingService:
    """Service for generating text embeddings using configurable providers."""

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self.api_key = settings.EMBEDDING_API_KEY
        self.base_url = settings.EMBEDDING_BASE_URL
        self._model = None

    def _get_model(self):
        """Get or create the embedding model."""
        if self._model is None:
            if self.provider == "sentence_transformers":
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model)
            elif self.provider == "openai":
                from openai import OpenAI
                self._model = OpenAI(
                    api_key=self.api_key or os.getenv("OPENAI_API_KEY"),
                    base_url=self.base_url or None
                )
            else:
                raise ValueError(f"Unsupported embedding provider: {self.provider}")
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        if self.provider == "sentence_transformers":
            model = self._get_model()
            embedding = model.encode(text.strip(), normalize_embeddings=True)
            return embedding.tolist()
        elif self.provider == "openai":
            client = self._get_model()
            response = client.embeddings.create(
                model=self.model,
                input=text.strip()
            )
            return response.data[0].embedding
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if self.provider == "sentence_transformers":
            model = self._get_model()
            embeddings = model.encode(
                [t.strip() for t in texts],
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False
            )
            return embeddings.tolist()
        elif self.provider == "openai":
            client = self._get_model()
            response = client.embeddings.create(
                model=self.model,
                input=[t.strip() for t in texts]
            )
            return [d.embedding for d in response.data]
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    def get_dimension(self) -> int:
        """Get the embedding dimension for the current model."""
        if self.provider == "sentence_transformers":
            model = self._get_model()
            return model.get_sentence_embedding_dimension()
        elif self.provider == "openai":
            # Common OpenAI embedding dimensions
            if "large" in self.model:
                return 3072
            elif "small" in self.model:
                return 1536
            else:
                return 1536
        return 384  # Default for all-MiniLM-L6-v2


# Singleton instance
_embedding_service: Optional["EmbeddingService"] = None


def get_embedding_service() -> "EmbeddingService":
    """Get the singleton EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service