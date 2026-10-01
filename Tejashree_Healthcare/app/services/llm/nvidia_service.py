"""
app/services/llm/nvidia_service.py

NVIDIA Nemotron LLM service for text-only health chat.
Uses NVIDIA's OpenAI-compatible API.
"""
import os
from typing import Optional
from openai import OpenAI
from openai import APIError, AuthenticationError, RateLimitError, APITimeoutError
from app.core.config import settings


# System prompt for healthcare assistant
HEALTH_SYSTEM_PROMPT = (
    "You are a GENERAL HEALTH INFORMATION ASSISTANT.\n"
    "You may explain general health concepts, medical terminology, summarize general health information, "
    "or describe common wellness topics.\n"
    "You must NOT diagnose diseases, claim certainty about a condition, prescribe medication, "
    "or pretend to be a doctor.\n"
    "For potentially urgent situations, encourage appropriate professional/emergency care.\n"
    "Always be helpful for general educational questions like 'What is blood pressure?'. "
    "Do not refuse normal educational questions.\n"
    "If a user asks about specific symptoms they are experiencing, provide general information "
    "about those symptoms and strongly encourage them to consult a healthcare professional.\n"
    "Never fabricate medical facts or cite non-existent studies."
)


class NvidiaLLMService:
    """Service for interacting with NVIDIA Nemotron via OpenAI-compatible API."""

    def __init__(self):
        self.api_key = settings.NVIDIA_API_KEY
        self.model = settings.NVIDIA_MODEL
        self.base_url = settings.NVIDIA_BASE_URL
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("NVIDIA_API_KEY is not configured")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=120.0,
            )
        return self._client

    def generate_response(self, user_message: str) -> str:
        """
        Generate a response from Nemotron for a health question.

        Args:
            user_message: The user's health question

        Returns:
            The model's response text

        Raises:
            ValueError: If API key is missing
            RuntimeError: For API errors, timeouts, or empty responses
        """
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is not configured")

        try:
            client = self._get_client()

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": HEALTH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            if not response.choices or not response.choices[0].message.content:
                raise RuntimeError("Received empty response from NVIDIA API")

            return response.choices[0].message.content.strip()

        except RuntimeError:
            # Re-raise our own RuntimeError (e.g., empty response)
            raise
        except AuthenticationError:
            raise RuntimeError("NVIDIA API authentication failed. Check your API key.")
        except RateLimitError:
            raise RuntimeError("NVIDIA API rate limit exceeded. Please try again later.")
        except APITimeoutError:
            raise RuntimeError("NVIDIA API request timed out. Please try again.")
        except APIError as e:
            raise RuntimeError(f"NVIDIA API error: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            # Don't expose internal details
            raise RuntimeError("Failed to generate response from AI service")


# Singleton instance
_nvidia_service: Optional[NvidiaLLMService] = None


def get_nvidia_service() -> NvidiaLLMService:
    """Get the singleton NvidiaLLMService instance."""
    global _nvidia_service
    if _nvidia_service is None:
        _nvidia_service = NvidiaLLMService()
    return _nvidia_service