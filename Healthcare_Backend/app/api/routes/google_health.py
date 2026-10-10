"""
app/api/routes/google_health.py

Google Health API OAuth routes.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.google_health import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    GoogleCallbackRequest,
    GoogleHealthConnectionStatus,
    GoogleHealthSyncRequest,
    GoogleHealthSyncResponse,
    GoogleDisconnectRequest,
    GoogleDisconnectResponse,
)
from app.services.google_health_service import get_google_health_service, GoogleHealthService, DEFAULT_SCOPES
from app.core.database import get_db
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fitness/google", tags=["Google Health"])


def get_current_user_id() -> int:
    """Get current user ID. TEMPORARY: uses environment variable."""
    return int(os.getenv("DEFAULT_USER_ID", "1"))


@router.get(
    "/authorize",
    response_model=GoogleAuthResponse,
    summary="Start Google Health OAuth authorization",
    description="Generate authorization URL for Google Health API access.",
)
async def authorize_google_health(
    scopes: Optional[List[str]] = Query(None, description="OAuth scopes to request"),
    db: Session = Depends(get_db),
) -> GoogleAuthResponse:
    """Start Google Health OAuth authorization flow."""
    service = get_google_health_service(db)
    auth_response = service.get_authorization_url(scopes=None)
    return auth_response


@router.get(
    "/callback",
    summary="Handle Google OAuth callback",
    description="Handle the OAuth callback from Google, exchange code for tokens.",
)
async def google_health_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OAuth callback from Google."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error} - {error_description or 'Unknown error'}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing code or state parameter",
        )

    # Get the expected state from session or query param
    # For simplicity, we'll get it from the query param
    # In production, you'd store state in a secure session
    expected_state = state

    service = get_google_health_service(db)

    try:
        # Exchange code for tokens
        token_data = service.exchange_code(code, state, expected_state)

        # Get user ID (temporary - from env)
        user_id = get_current_user_id()

        # Store tokens
        service.store_tokens(user_id, token_data, DEFAULT_SCOPES)

        # Return success page or redirect
        return {
            "message": "Successfully connected to Google Health",
            "connected": True,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete OAuth flow",
        )


@router.get(
    "/status",
    response_model=GoogleHealthConnectionStatus,
    summary="Check Google Health connection status",
    description="Check if the user is connected to Google Health and token status.",
)
async def google_health_status(
    db: Session = Depends(get_db),
) -> GoogleHealthConnectionStatus:
    """Check Google Health connection status."""
    user_id = get_current_user_id()
    service = get_google_health_service(db)
    return service.get_connection_status(user_id)


@router.post(
    "/sync",
    response_model=GoogleHealthSyncResponse,
    summary="Sync fitness data from Google Health",
    description="Synchronize steps and sleep data from Google Health API.",
)
async def sync_google_health(
    sync_request: GoogleHealthSyncRequest,
    db: Session = Depends(get_db),
) -> GoogleHealthSyncResponse:
    """Sync fitness data from Google Health API."""
    user_id = get_current_user_id()
    service = get_google_health_service(db)

    start_date = None
    end_date = None
    if sync_request.start_date:
        start_date = datetime.fromisoformat(sync_request.start_date.replace("Z", "+00:00"))
    if sync_request.end_date:
        end_date = datetime.fromisoformat(sync_request.end_date.replace("Z", "+00:00"))

    result = await service.sync_fitness_data(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        data_types=sync_request.data_types,
    )

    return GoogleHealthSyncResponse(
        success=result.get("success", False),
        records_synced=result.get("records_synced", 0),
        steps_synced=result.get("steps_synced", 0),
        sleep_records_synced=result.get("sleep_records_synced", 0),
        start_date=result.get("start_date"),
        end_date=result.get("end_date"),
        error_message=result.get("error"),
    )


@router.delete(
    "/disconnect",
    response_model=GoogleDisconnectResponse,
    summary="Disconnect Google Health",
    description="Disconnect Google Health and optionally revoke tokens.",
)
async def disconnect_google_health(
    disconnect_request: GoogleDisconnectRequest,
    db: Session = Depends(get_db),
) -> GoogleDisconnectResponse:
    """Disconnect Google Health integration."""
    user_id = get_current_user_id()
    service = get_google_health_service(db)

    success = service.revoke_tokens(user_id)

    return GoogleDisconnectResponse(
        success=success,
        message="Google Health disconnected successfully" if success else "No active connection to disconnect",
    )