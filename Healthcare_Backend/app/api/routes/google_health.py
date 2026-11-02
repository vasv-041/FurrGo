"""
app/api/routes/google_health.py

Google Health API OAuth routes with JWT authentication and OAuth state binding.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.google_health import (
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
from app.api.deps import get_current_user
from app.api.deps import store_oauth_state, get_oauth_state, invalidate_oauth_state
import os
import logging
import secrets
import string

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fitness/google", tags=["Google Health"])


@router.get(
    "/authorize",
    response_model=GoogleAuthResponse,
    summary="Start Google Health OAuth authorization",
    description="Generate authorization URL for Google Health API access.",
)
async def authorize_google_health(
    scopes: Optional[List[str]] = Query(None, description="OAuth scopes to request"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoogleAuthResponse:
    """Start Google Health OAuth authorization flow."""
    service = get_google_health_service(db)
    
    # Generate a cryptographically random state token
    state_token = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Bind the state to the initiating user
    store_oauth_state(state_token, current_user.id, db, expiry_minutes=10)
    
    # Generate authorization URL - we'll construct a proper one
    # For now, return the state that the client should use
    auth_response = service.get_authorization_url(scopes=None)
    
    # Add the state parameter to the response so the frontend can use it
    # The client will pass this state to the callback
    return {
        "message": "Authorization URL generated",
        "connected": False,
        "authorization_url": auth_response.authorization_url,
        "state": state_token,
        "expires_in": 600  # 10 minutes in seconds
    }


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
) -> dict:
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

    # Look up the state from the server-side store
    # This independently validates the state, regardless of what's in the callback
    user_id = get_oauth_state(state)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )
    
    service = get_google_health_service(db)

    try:
        # Exchange code for tokens
        token_data = service.exchange_code(code, state, state)

        # Store tokens for the authenticated user from the initial authorization
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
    current_user: User = Depends(get_current_user),
) -> GoogleHealthConnectionStatus:
    """Check Google Health connection status."""
    user_id = current_user.id
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
    current_user: User = Depends(get_current_user),
) -> GoogleHealthSyncResponse:
    """Sync fitness data from Google Health API."""
    user_id = current_user.id
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
    current_user: User = Depends(get_current_user),
) -> GoogleDisconnectResponse:
    """Disconnect Google Health integration."""
    user_id = current_user.id
    service = get_google_health_service(db)

    success = service.revoke_tokens(user_id)

    return GoogleDisconnectResponse(
        success=success,
        message="Google Health disconnected successfully" if success else "No active connection to disconnect",
    )
