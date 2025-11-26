"""
Authentication API Endpoints
Handles Google OAuth token exchange
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import structlog

from app.config import settings
from app.auth import create_access_token

logger = structlog.get_logger()
router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleTokenRequest(BaseModel):
    token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleTokenRequest):
    """
    Exchange Google OAuth token for JWT access token

    This endpoint:
    1. Verifies the Google ID token
    2. Checks the user's domain is @enterprisesight.com
    3. Returns a JWT for API authentication
    """
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            request.token,
            requests.Request(),
            settings.google_oauth_client_id
        )

        # Verify the issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer"
            )

        # Verify domain
        email = idinfo.get('email', '')
        domain = email.split('@')[-1] if '@' in email else ''

        if domain != settings.allowed_domain:
            logger.warning(
                "auth_domain_rejected",
                email=email,
                domain=domain,
                allowed=settings.allowed_domain,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only @{settings.allowed_domain} users are allowed"
            )

        # Extract user info
        user_data = {
            "email": email,
            "name": idinfo.get('name', ''),
            "picture": idinfo.get('picture', ''),
            "user_id": idinfo.get('sub', ''),
        }

        # Create JWT token
        token_data = {
            "sub": email,  # Use email as the subject
            "email": email,
            "name": user_data["name"],
            "picture": user_data["picture"],
        }
        access_token = create_access_token(token_data)

        logger.info(
            "user_authenticated",
            email=email,
            name=user_data["name"],
        )

        return AuthResponse(
            access_token=access_token,
            user=user_data,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("google_token_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    except Exception as e:
        logger.error("auth_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me")
async def get_current_user_info():
    """
    Get current user info (placeholder - requires auth middleware)
    """
    return {"message": "Use Authorization header with JWT token"}
