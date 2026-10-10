"""
app/services/google_health_service.py

Google Health API OAuth service and fitness data synchronization.
"""
import secrets
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, parse_qs

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.google_health_token import GoogleHealthToken
from app.models.user import User
from app.schemas.google_health import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleCallbackRequest,
    GoogleTokenResponse,
    GoogleIdentityResponse,
    GoogleHealthConnectionStatus,
    GoogleHealthSyncRequest,
    GoogleHealthSyncResponse,
    GoogleDisconnectResponse,
    GoogleHealthScope,
)
from app.models.fitness import FitnessData, FitnessSource

logger = logging.getLogger(__name__)


# Google Health API endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_HEALTH_API_BASE = "https://health.googleapis.com/v4"
GOOGLE_IDENTITY_URL = f"{GOOGLE_HEALTH_API_BASE}/users/getIdentity"

# Required scopes for fitness data
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
]

# Encryption key for token storage (in production, use a proper key management system)
# For development, derive from a secret; in production, use a proper KMS
def _get_encryption_key() -> bytes:
    """Get or derive encryption key for token storage."""
    # In production, this should come from a secure key management system
    # For now, derive from a secret in settings
    secret = getattr(settings, "TOKEN_ENCRYPTION_KEY", "dev-secret-change-in-production-32chars!")
    # Pad or truncate to 32 bytes for Fernet
    key = base64.urlsafe_b64encode(secret.encode()[:32].ljust(32, b'0'))
    return key


class TokenEncryption:
    """Handle token encryption/decryption for secure storage."""

    def __init__(self):
        self._fernet = Fernet(_get_encryption_key())

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        ciphertext = self._fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(ciphertext).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        plaintext = self._fernet.decrypt(encrypted)
        return plaintext.decode()


class GoogleHealthService:
    """Service for Google Health API OAuth and data synchronization."""

    def __init__(self, db: Session):
        self.db = db
        self.encryption = TokenEncryption()

    # ==================== OAuth Flow ====================

    def get_authorization_url(self, scopes: Optional[List[str]] = None) -> GoogleAuthResponse:
        """Generate Google OAuth authorization URL with CSRF state."""
        if scopes is None:
            scopes = DEFAULT_SCOPES

        # Generate CSRF state token
        state = secrets.token_urlsafe(32)

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

        return GoogleAuthResponse(
            authorization_url=auth_url,
            state=state,
        )

    def exchange_code(self, code: str, state: str, expected_state: str) -> GoogleTokenResponse:
        """Exchange authorization code for tokens."""
        if state != expected_state:
            raise ValueError("Invalid state parameter (CSRF protection)")

        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            raise ValueError(f"Token exchange failed: {response.text}")

        data = response.json()
        return GoogleTokenResponse(**data)

    async def store_tokens(
        self,
        user_id: int,
        token_data: GoogleTokenResponse,
        scopes: List[str],
    ) -> GoogleHealthToken:
        """Store encrypted tokens in database."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data.expires_in)

        token = GoogleHealthToken(
            user_id=user_id,
            access_token=self.encryption.encrypt(token_data.access_token),
            refresh_token=self.encryption.encrypt(token_data.refresh_token),
            expires_at=expires_at,
            scopes=",".join(scopes),
            is_active=True,
        )

        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    async def get_user_tokens(self, user_id: int) -> Optional[GoogleHealthToken]:
        """Get active tokens for a user."""
        return self.db.query(GoogleHealthToken).filter(
            GoogleHealthToken.user_id == user_id,
            GoogleHealthToken.is_active == True,
        ).first()

    def _decrypt_tokens(self, token: GoogleHealthToken) -> tuple[str, str]:
        """Decrypt stored tokens."""
        access_token = self.encryption.decrypt(token.access_token)
        refresh_token = self.encryption.decrypt(token.refresh_token)
        return access_token, refresh_token

    async def refresh_access_token(self, token: GoogleHealthToken) -> str:
        """Refresh access token using refresh token."""
        _, refresh_token = self._decrypt_tokens(token)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30.0,
            )

        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.text}")
            raise ValueError(f"Token refresh failed: {response.text}")

        data = response.json()
        new_access_token = data["access_token"]
        new_expires_in = data.get("expires_in", 3600)

        # Update token in database
        token.access_token = self.encryption.encrypt(new_access_token)
        token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)
        token.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return new_access_token

    async def get_valid_access_token(self, user_id: int) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        token = await self.get_user_tokens(user_id)
        if not token:
            return None

        # Check if token is expired or expiring soon (within 5 minutes)
        if token.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            return await self.refresh_access_token(token)

        return self.encryption.decrypt(token.access_token)

    async def get_identity(self, access_token: str) -> GoogleIdentityResponse:
        """Get user identity from Google Health API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_IDENTITY_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )

        if response.status_code != 200:
            logger.error(f"Get identity failed: {response.text}")
            raise ValueError(f"Get identity failed: {response.text}")

        data = response.json()
        return GoogleIdentityResponse(
            google_user_id=data.get("googleUserId", ""),
            fitbit_user_id=data.get("fitbitUserId"),
        )

    def revoke_tokens(self, user_id: int) -> bool:
        """Revoke and deactivate user's tokens."""
        token = self.db.query(GoogleHealthToken).filter(
            GoogleHealthToken.user_id == user_id,
            GoogleHealthToken.is_active == True,
        ).first()

        if not token:
            return False

        # Optionally revoke at Google (optional, but good practice)
        try:
            access_token = self.encryption.decrypt(token.access_token)
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": access_token},
                timeout=10.0,
            )
        except Exception as e:
            logger.warning(f"Failed to revoke token at Google: {e}")

        # Deactivate locally
        token.is_active = False
        token.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def get_connection_status(self, user_id: int) -> GoogleHealthConnectionStatus:
        """Get Google Health connection status for a user."""
        token = self.db.query(GoogleHealthToken).filter(
            GoogleHealthToken.user_id == user_id,
        ).first()

        if not token or not token.is_active:
            return GoogleHealthConnectionStatus(
                connected=False,
                scopes=[],
            )

        # Try to get identity to verify connection
        google_user_id = None
        try:
            access_token = self.encryption.decrypt(token.access_token)
            # We'll do this async in the API route
        except Exception:
            pass

        return GoogleHealthConnectionStatus(
            connected=token.is_active,
            scopes=token.scopes.split(",") if token.scopes else [],
            expires_at=token.expires_at.isoformat() if token.expires_at else None,
            last_sync_at=token.last_sync_at.isoformat() if token.last_sync_at else None,
            google_user_id=google_user_id,
        )

    # ==================== Fitness Data Synchronization ====================

    async def sync_fitness_data(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        data_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Sync fitness data from Google Health API."""
        if data_types is None:
            data_types = ["steps", "sleep"]

        access_token = await self.get_valid_access_token(user_id)
        if not access_token:
            return {"success": False, "error": "No valid access token"}

        # Default to last 30 days if no dates provided
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        results = {
            "success": True,
            "records_synced": 0,
            "steps_synced": 0,
            "sleep_records_synced": 0,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Sync steps
            if "steps" in data_types:
                steps_result = await self._sync_steps(client, headers, user_id, start_date, end_date)
                results["steps_synced"] = steps_result.get("synced", 0)
                results["records_synced"] += steps_result.get("synced", 0)

            # Sync sleep
            if "sleep" in data_types:
                sleep_result = await self._sync_sleep(client, headers, user_id, start_date, end_date)
                results["sleep_records_synced"] = sleep_result.get("synced", 0)
                results["records_synced"] += sleep_result.get("synced", 0)

        # Update last sync time
        token = await self.get_user_tokens(user_id)
        if token:
            token.last_sync_at = datetime.now(timezone.utc)
            self.db.commit()

        return results

    async def _sync_steps(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, int]:
        """Sync steps data using dailyRollUp."""
        synced = 0
        current_date = start_date

        while current_date <= end_date:
            # Format date for dailyRollUp
            start_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
            end_time = current_date.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z"

            url = f"{GOOGLE_HEALTH_API_BASE}/users/me/dataTypes/steps/dataPoints:dailyRollUp"
            params = {
                "range.startTime": start_time,
                "range.endTime": end_time,
                "windowSizeDays": 1,
            }

            try:
                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    # Process and store steps data
                    synced += self._process_steps_data(user_id, current_date, data)
                elif response.status_code == 401:
                    raise ValueError("Access token expired")
            except Exception as e:
                logger.warning(f"Failed to sync steps for {current_date.date()}: {e}")

            current_date += timedelta(days=1)

        return {"synced": synced}

    async def _sync_sleep(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, int]:
        """Sync sleep data using dailyRollUp."""
        synced = 0
        current_date = start_date

        while current_date <= end_date:
            start_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
            end_time = current_date.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z"

            url = f"{GOOGLE_HEALTH_API_BASE}/users/me/dataTypes/sleep/dataPoints:dailyRollUp"
            params = {
                "range.startTime": start_time,
                "range.endTime": end_time,
                "windowSizeDays": 1,
            }

            try:
                response = await client.get(url, headers=headers, params=params, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    synced += self._process_sleep_data(user_id, current_date, data)
                elif response.status_code == 401:
                    raise ValueError("Access token expired")
            except Exception as e:
                logger.warning(f"Failed to sync sleep for {current_date.date()}: {e}")

            current_date += timedelta(days=1)

        return {"synced": synced}

    def _extract_steps_from_daily_rollup(self, data: Dict) -> Optional[int]:
        """Extract steps count from dailyRollUp response."""
        try:
            # Google Health API dailyRollUp response format
            if "dailyRollups" in data:
                for rollup in data["dailyRollups"]:
                    if "data" in rollup:
                        for point in rollup["data"]:
                            if "value" in point and "intVal" in point["value"]:
                                return point["value"]["intVal"]
            return None
        except Exception:
            return None

    def _extract_sleep_duration_from_rollup(self, data: Dict) -> Optional[int]:
        """Extract total sleep duration in minutes from dailyRollUp response."""
        try:
            total_minutes = 0
            if "dailyRollups" in data:
                for rollup in data["dailyRollups"]:
                    if "data" in rollup:
                        for point in rollup["data"]:
                            if "sleepStage" in point:
                                stage = point["sleepStage"]
                                duration = point.get("duration", {})
                                if "seconds" in duration:
                                    total_minutes += int(duration["seconds"]) // 60
            return total_minutes if total_minutes > 0 else None
        except Exception:
            return None

    def _process_steps_data(self, user_id: int, date: datetime, data: Dict) -> int:
        """Process steps dailyRollUp response and store in FitnessData."""
        synced = 0
        try:
            # Parse the dailyRollUp response
            steps_count = self._extract_steps_from_daily_rollup(data)
            if steps_count is not None and steps_count > 0:
                # Create or update FitnessData record
                from app.services.fitness_service import FitnessService
                from app.schemas.fitness import FitnessDataCreate, FitnessSource

                fitness_service = FitnessService(self.db)
                existing = self.db.query(FitnessData).filter(
                    FitnessData.user_id == user_id,
                    FitnessData.date == date.date(),
                    FitnessData.source == FitnessSource.GOOGLE_FIT,
                ).first()

                if existing:
                    existing.steps = steps_count
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    fitness_data = FitnessDataCreate(
                        user_id=user_id,
                        recorded_at=datetime.combine(date.date(), datetime.min.time()).replace(tzinfo=timezone.utc),
                        steps=steps_count,
                        source=FitnessSource.GOOGLE_FIT,
                    )
                    fitness_service.create_fitness_data(fitness_data)
                synced = 1
        except Exception as e:
            logger.warning(f"Failed to process steps data: {e}")
        return synced

    def _process_sleep_data(self, user_id: int, date: datetime, data: Dict) -> int:
        """Process sleep dailyRollUp response and store in FitnessData."""
        synced = 0
        try:
            from app.services.fitness_service import FitnessService
            from app.schemas.fitness import FitnessDataCreate, FitnessSource

            sleep_duration = self._extract_sleep_duration_from_rollup(data)
            if sleep_duration is not None and sleep_duration > 0:
                fitness_service = FitnessService(self.db)
                existing = self.db.query(FitnessData).filter(
                    FitnessData.user_id == user_id,
                    FitnessData.date == date.date(),
                    FitnessData.source == FitnessSource.GOOGLE_FIT,
                ).first()

                if existing:
                    existing.sleep_duration = sleep_duration
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    fitness_data = FitnessDataCreate(
                        user_id=user_id,
                        recorded_at=datetime.combine(date.date(), datetime.min.time()).replace(tzinfo=timezone.utc),
                        sleep_duration=sleep_duration,
                        source=FitnessSource.GOOGLE_FIT,
                    )
                    fitness_service.create_fitness_data(fitness_data)
                synced = 1
        except Exception as e:
            logger.warning(f"Failed to process sleep data: {e}")
        return synced


# Module-level service instance
_google_health_service: Optional[GoogleHealthService] = None


def get_google_health_service(db: Session) -> GoogleHealthService:
    """Get or create GoogleHealthService instance."""
    return GoogleHealthService(db)