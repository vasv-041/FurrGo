"""
app/schemas/google_health.py

Google Health API OAuth schemas.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
from enum import Enum


class GoogleHealthScope(str, Enum):
    """Google Health API OAuth scopes."""
    ACTIVITY_AND_FITNESS_READONLY = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"
    SLEEP_READONLY = "https://www.googleapis.com/auth/googlehealth.sleep.readonly"
    HEALTH_METRICS_AND_MEASUREMENTS_READONLY = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
    PROFILE_READONLY = "https://www.googleapis.com/auth/googlehealth.profile.readonly"
    SETTINGS_READONLY = "https://www.googleapis.com/auth/googlehealth.settings.readonly"


# Default read-only scopes for fitness data
DEFAULT_FITNESS_SCOPES = [
    GoogleHealthScope.ACTIVITY_AND_FITNESS_READONLY,
    GoogleHealthScope.SLEEP_READONLY,
]


class GoogleAuthRequest(BaseModel):
    """Request to start Google OAuth flow."""
    scopes: Optional[List[str]] = None

    @field_validator("scopes", mode="before")
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> List[str]:
        if v is None:
            return [s.value for s in DEFAULT_FITNESS_SCOPES]
        return v


class GoogleAuthResponse(BaseModel):
    """Response with authorization URL."""
    authorization_url: str
    state: str


class GoogleCallbackRequest(BaseModel):
    """Callback query parameters from Google OAuth."""
    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


class GoogleTokenResponse(BaseModel):
    """Token exchange response from Google."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str
    id_token: Optional[str] = None


class GoogleIdentityResponse(BaseModel):
    """Google Health API identity response."""
    google_user_id: str
    fitbit_user_id: Optional[str] = None


class GoogleHealthConnectionStatus(BaseModel):
    """Google Health connection status."""
    connected: bool
    scopes: List[str]
    expires_at: Optional[str] = None
    last_sync_at: Optional[str] = None
    google_user_id: Optional[str] = None


class GoogleHealthSyncRequest(BaseModel):
    """Request to sync fitness data from Google Health."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    data_types: Optional[List[str]] = None  # e.g., ["steps", "sleep"]


class GoogleHealthSyncResponse(BaseModel):
    """Response from fitness data sync."""
    success: bool
    records_synced: int
    steps_synced: int
    sleep_records_synced: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    error_message: Optional[str] = None


class GoogleDisconnectRequest(BaseModel):
    """Request to disconnect Google Health."""
    revoke_tokens: bool = True


class GoogleDisconnectResponse(BaseModel):
    """Response from disconnect."""
    success: bool
    message: str