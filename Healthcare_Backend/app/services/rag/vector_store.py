"""
app/services/rag/vector_store.py

ChromaDB vector store service for RAG document pipeline.
Provides persistent local vector storage with similarity search.
"""

import os
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings


class VectorStoreService:
    """ChromaDB vector store service for RAG document storage and retrieval."""

    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self._client = None
        self._collection = None

    def _get_client(self) -> chromadb.Client:
        """Get or create ChromaDB client."""
        if self._client is None:
            # Ensure persist directory exists
            os.makedirs(self.persist_dir, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        return self._client

    def _get_collection(self):
        """Get or create the documents collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name="healthcare_documents",
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def add_chunks(
        self,
        document_id: int,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]]
    ) -> None:
        """
        Add document chunks with embeddings to the vector store.

        Args:
            document_id: Database ID of the source document
            chunks: List of text chunks
            embeddings: List of embedding vectors (one per chunk)
            metadata: List of metadata dicts for each chunk
        """
        if not chunks or not embeddings:
            return

        collection = self._get_collection()

        # Generate unique IDs for each chunk
        ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]

        # Prepare metadata with document_id
        chunk_metadata = []
        for i, meta in enumerate(metadata):
            chunk_meta = {
                "document_id": document_id,
                "chunk_index": i,
                "source_type": "pdf",
                **meta
            }
            chunk_metadata.append(chunk_meta)

        # Add to collection
        self._collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=chunk_metadata
        )

    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 5,
        document_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            document_ids: Optional list of document IDs to filter by

        Returns:
            List of matching chunks with metadata and similarity scores
        """
        collection = self._get_collection()

        # Build where clause for document filtering
        where_clause = None
        if document_ids:
            where_clause = {"document_id": {"$in": document_ids}}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        results_list = []
        for i, doc in enumerate(results["documents"][0]):
            results_list.append({
                "content": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i]  # cosine similarity
            })

        return results_list

    def get_document_chunks(self, document_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document."""
        collection = self._get_collection()

        results = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"]
        )

        if not results["documents"]:
            return []

        results_list = []
        for i, doc in enumerate(results["documents"]):
            results_list.append({
                "content": doc,
                "metadata": results["metadatas"][i]
            })

        return results_list

    def delete_document(self, document_id: int) -> None:
        """Delete all chunks for a document."""
        collection = self._get_collection()
        collection.delete(where={"document_id": document_id})


# Singleton instance
_vector_store: Optional["VectorStoreService"] = None


def get_vector_store() -> "VectorStoreService":
    """Get the singleton VectorStoreService instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
    return _vector_store