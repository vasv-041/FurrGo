"""
app/services/langchain/chains.py

LangChain chains for healthcare chat.
Implements TextOnlyChain and RAGChain using existing services.
"""
from typing import Any, Dict, List, Optional
from langchain_core.runnables import Runnable, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

from app.services.langchain.adapters import NemotronAdapter
from app.services.langchain.prompts import TEXT_ONLY_PROMPT, RAG_PROMPT
from app.services.langchain.retriever import create_health_retriever
from app.services.safety.health_safety import get_safety_validator


def create_text_only_chain() -> Runnable:
    """
    Create a text-only health chat chain.
    
    Flow:
    user message -> prompt -> Nemotron adapter -> SafetyValidator -> final response
    """
    adapter = NemotronAdapter()
    safety_validator = get_safety_validator()
    
    def apply_safety(input_dict: Dict[str, Any]) -> Dict[str, Any]:
        message = input_dict.get("message", "")
        model_response = input_dict.get("model_response", "")
        safe_response = safety_validator.process_response(message, model_response)
        return {"response": safe_response}
    
    # Build the chain: message -> prompt -> adapter -> output_parser -> safety -> response
    chain = (
        RunnablePassthrough.assign(
            model_response=TEXT_ONLY_PROMPT | adapter | StrOutputParser()
        )
        | RunnableLambda(lambda x: {"response": safety_validator.process_response(x["message"], x["model_response"])})
    )
    
    return chain


def create_rag_chain(document_ids: Optional[List[int]] = None, k: int = 5) -> Runnable:
    """
    Create a RAG health chat chain.
    
    Flow:
    user message -> retriever -> retrieved context -> RAG prompt -> Nemotron adapter -> SafetyValidator -> final response
    """
    retriever = create_health_retriever(k=k, document_ids=document_ids)
    adapter = NemotronAdapter()
    safety_validator = get_safety_validator()
    
    def format_docs(docs):
        """Format retrieved documents into context string."""
        return "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    # Build the chain
    chain = (
        RunnablePassthrough.assign(
            context=lambda x: format_docs(retriever.get_relevant_documents(x["message"]))
        )
        | RunnablePassthrough.assign(
            model_response=RAG_PROMPT | adapter | StrOutputParser()
        )
        | RunnableLambda(lambda x: {"response": safety_validator.process_response(x["message"], x["model_response"])})
    )
    
    return chain