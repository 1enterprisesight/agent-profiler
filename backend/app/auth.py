"""
Authentication and authorization
Google Workspace OAuth 2.0 for @enterprisesight.com users
"""

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://accounts.google.com/o/oauth2/v2/auth",
    tokenUrl=f"https://oauth2.googleapis.com/token",
)


class TokenData(BaseModel):
    """Token payload data"""
    email: str
    user_id: str
    name: Optional[str] = None
    picture: Optional[str] = None


class User(BaseModel):
    """Authenticated user"""
    email: str
    user_id: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_admin: bool = False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Token payload
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


async def verify_google_token(token: str) -> dict:
    """
    Verify Google OAuth token

    Args:
        token: Google ID token

    Returns:
        Token payload with user info

    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.google_oauth_client_id
        )

        # Verify the issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        # Verify domain
        email = idinfo.get('email', '')
        domain = email.split('@')[-1] if '@' in email else ''

        if domain != settings.allowed_domain:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only {settings.allowed_domain} users are allowed"
            )

        return idinfo

    except ValueError as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get current authenticated user from token

    Args:
        token: JWT token from request

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not authorized
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        email: str = payload.get("email")
        user_id: str = payload.get("sub")

        if email is None or user_id is None:
            raise credentials_exception

        token_data = TokenData(
            email=email,
            user_id=user_id,
            name=payload.get("name"),
            picture=payload.get("picture")
        )

    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise credentials_exception

    # Verify domain again
    domain = token_data.email.split('@')[-1] if '@' in token_data.email else ''
    if domain != settings.allowed_domain:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only {settings.allowed_domain} users are allowed"
        )

    # Create user object
    user = User(
        email=token_data.email,
        user_id=token_data.user_id,
        name=token_data.name,
        picture=token_data.picture,
        is_admin=False  # TODO: Implement admin role logic
    )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional checks can be added here)

    Args:
        current_user: User from token

    Returns:
        User object
    """
    # Add additional checks here if needed
    # For example: check if user is active in database
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require admin privileges

    Args:
        current_user: Current authenticated user

    Returns:
        User object if admin

    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Helper function to check if email is from allowed domain
def is_allowed_email(email: str) -> bool:
    """
    Check if email is from allowed domain

    Args:
        email: Email address to check

    Returns:
        True if email is from allowed domain
    """
    domain = email.split('@')[-1] if '@' in email else ''
    return domain == settings.allowed_domain
