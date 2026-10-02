"""
app/services/langchain/adapters.py

LangChain-compatible adapter around the existing Nemotron service.
Wraps the existing NvidiaLLMService to provide a LangChain-compatible interface.
"""
from typing import Any, AsyncIterator, Iterator, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.services.llm.nvidia_service import get_nvidia_service


class NemotronAdapter(BaseChatModel):
    """
    LangChain-compatible adapter for the existing Nemotron service.
    Wraps the existing NvidiaLLMService without duplicating its implementation.
    """

    model_name: str = Field(default="nemotron-3.5-lightning-30b-a3b")
    temperature: float = Field(default=0.3)
    max_tokens: int = Field(default=1024)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service = get_nvidia_service()

    @property
    def _llm_type(self) -> str:
        return "nvidia-nemotron"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response from Nemotron."""
        # Convert LangChain messages to the format expected by existing service
        # The existing service expects a single user message string
        # We'll combine system and user messages
        system_content = ""
        user_content = ""
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_content = msg.content
            elif isinstance(msg, HumanMessage):
                user_content = msg.content
            elif isinstance(msg, AIMessage):
                # For simplicity, we'll treat AI messages as part of conversation history
                # In a more complete implementation, we might handle conversation history
                pass
        
        # Combine system prompt with user message if needed
        # The existing service already includes HEALTH_SYSTEM_PROMPT internally
        # So we just pass the user message
        combined_message = user_content
        
        try:
            response_text = self._service.generate_response(combined_message)
            
            generation = ChatGeneration(
                message=AIMessage(content=response_text),
                text=response_text,
            )
            return ChatResult(generations=[generation])
        except ValueError:
            # Re-raise ValueError (e.g., missing API key) as-is
            raise
        except Exception as e:
            # Re-raise with context for other exceptions
            raise RuntimeError(f"Nemotron adapter error: {str(e)}") from e

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async version - runs sync generate in thread pool."""
        import asyncio
        return await asyncio.to_thread(self._generate, messages, stop, run_manager, **kwargs)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        """Stream not supported - delegate to _generate."""
        result = self._generate(messages, stop, run_manager, **kwargs)
        for gen in result.generations:
            yield gen

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGeneration]:
        """Async stream not supported - delegate to _agenerate."""
        result = await self._agenerate(messages, stop, run_manager, **kwargs)
        for gen in result.generations:
            yield gen