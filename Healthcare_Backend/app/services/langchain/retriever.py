"""
app/services/langchain/retriever.py

LangChain-compatible retriever around the EXISTING ChromaDB and embedding service.
Reuses existing get_vector_store() and get_embedding_service().
"""
from typing import Any, List, Optional
from langchain_core.documents import Document as LangChainDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from app.services.rag.vector_store import get_vector_store
from app.services.rag.embeddings import get_embedding_service


class HealthRetriever(BaseRetriever):
    """
    LangChain-compatible retriever around existing ChromaDB and embedding service.
    Reuses existing vector store and embedding service.
    """
    
    vector_store: Any = Field(default=None, exclude=True)
    embedding_service: Any = Field(default=None, exclude=True)
    k: int = Field(default=5)
    document_ids: Optional[List[int]] = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vector_store = get_vector_store()
        self.embedding_service = get_embedding_service()
    
    def _get_relevant_documents(self, query: str) -> List[LangChainDocument]:
        """Retrieve relevant documents for the query."""
        # Generate query embedding using existing embedding service
        query_embedding = self.embedding_service.generate_embedding(query)
        
        # Search using existing vector store
        results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            k=self.k,
            document_ids=self.document_ids
        )
        
        # Convert to LangChain Documents
        documents = []
        for result in results:
            metadata = result.get("metadata", {})
            doc = LangChainDocument(
                page_content=result["content"],
                metadata={
                    "document_id": metadata.get("document_id"),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "source_type": metadata.get("source_type", "pdf"),
                    "original_filename": metadata.get("original_filename", ""),
                    "distance": result.get("distance"),
                    "similarity": result.get("similarity"),
                }
            )
            documents.append(doc)
        
        return documents
    
    async def _aget_relevant_documents(self, query: str) -> List[LangChainDocument]:
        """Async version - runs sync retrieve in thread pool."""
        import asyncio
        return await asyncio.to_thread(self._get_relevant_documents, query)


def create_health_retriever(
    k: int = 5,
    document_ids: Optional[List[int]] = None
) -> HealthRetriever:
    """Factory function to create a configured HealthRetriever."""
    return HealthRetriever(k=k, document_ids=document_ids)