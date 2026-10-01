"""
app/core/config.py

Application configuration using Pydantic Settings.
Reads values from environment variables / .env file.
Placeholders for future phases are included but not required now.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Healthcare Monitoring Assistant."""

    # ------------------------------------------------------------------ #
    # Application metadata
    # ------------------------------------------------------------------ #
    APP_NAME: str = "Healthcare Monitoring Assistant"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ------------------------------------------------------------------ #
    # Server settings
    # ------------------------------------------------------------------ #
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ------------------------------------------------------------------ #
    # Future phase placeholders (optional — not required in Phase 1)
    # ------------------------------------------------------------------ #
    # Phase 2 — AI / LLM integration (Gemini for image/PDF — later phase)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Phase 3 — NVIDIA Nemotron (text-only chat)
    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Phase 3 — Database
    DATABASE_URL: str = "sqlite:///./data/health_ai.db"

    # Phase 4 — File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Phase 5 — External health integrations
    HEALTH_INTEGRATION_API_KEY: str = ""

    # ------------------------------------------------------------------ #
    # Pydantic Settings config
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",          # silently ignore unknown env vars
    )


# Single shared instance — import this everywhere
settings = Settings()
