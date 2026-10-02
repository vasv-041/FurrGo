"""
app/api/routes/chat.py

Health chat endpoint supporting text-only and RAG queries.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm.nvidia_service import get_nvidia_service
from app.services.safety.health_safety import get_safety_validator
from app.services.rag.vector_store import get_vector_store
from app.services.rag.embeddings import get_embedding_service
from app.core.database import get_db
from app.core.config import settings

router = APIRouter(tags=["Chat"])

# Maximum message length
MAX_MESSAGE_LENGTH = 2000


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Chat with Health Assistant",
    description="Send a text message with optional document_id for RAG queries.",
)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db)
) -> ChatResponse:
    """
    POST /api/chat

    Multimodal health chat:
    - Text only → NVIDIA Nemotron
    - Text + document_id → RAG retrieval + Nemotron
    """
    # Input validation
    message = request.message.strip() if request.message else ""

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters."
        )

    # Get services
    nvidia_service = get_nvidia_service()
    safety_validator = get_safety_validator()
    vector_store = get_vector_store()
    embedding_service = get_embedding_service()

    try:
        sources = []

        if request.document_id:
            # RAG flow: retrieve relevant chunks and use as context
            query_embedding = get_embedding_service().generate_embedding(message)

            results = vector_store.similarity_search(
                query_embedding=query_embedding,
                k=5,
                document_ids=[request.document_id]
            )

            if results:
                # Build context from retrieved chunks
                context_parts = []
                for result in results:
                    metadata = result.get("metadata", {})
                    sources.append({
                        "document_id": metadata.get("document_id"),
                        "page_number": metadata.get("page_number", 1),
                        "chunk_index": metadata.get("chunk_index", 0)
                    })
                    context_parts.append(f"[Source: doc {metadata.get('document_id')}, page {metadata.get('page_number', 1)}, chunk {metadata.get('chunk_index', 0)}]\n{result['content']}")

                context = "\n\n---\n\n".join(context_parts)
                augmented_message = f"Context from uploaded document:\n\n{context}\n\nQuestion: {message}"
                model_response = nvidia_service.generate_response(augmented_message)
            else:
                # No relevant chunks found
                model_response = "The uploaded document does not contain information relevant to your question. I cannot answer based on this document alone."
        else:
            # Text only → Nemotron
            model_response = nvidia_service.generate_response(message)

        # Safety processing
        final_response = safety_validator.process_response(message, model_response)

        # Extract disclaimer (it's always appended by safety validator)
        disclaimer = "This information is general health information and is not a diagnosis or a substitute for professional medical advice."

        return ChatResponse(
            response=final_response,
            disclaimer=disclaimer,
            model=settings.NVIDIA_MODEL,
            sources=sources
        )

    except ValueError as e:
        # Missing API key
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Please contact administrator."
        )
    except RuntimeError as e:
        # API errors, timeouts, etc.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors - don't expose internals
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )
