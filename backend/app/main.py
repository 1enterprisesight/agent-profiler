"""
Agent Profiler - Main FastAPI Application
Multi-agent AI system for client data analysis with complete transparency
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import structlog
from datetime import datetime

from app.config import settings
from app.database import init_db, close_db
from app.auth import get_current_user, User

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("application_starting", env=settings.app_env)
    await init_db()
    logger.info("application_started")

    yield

    # Shutdown
    logger.info("application_stopping")
    await close_db()
    logger.info("application_stopped")


# Create FastAPI application
app = FastAPI(
    title="Agent Profiler API",
    description="Multi-agent AI system for client data analysis with complete transparency",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Configure CORS
if settings.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Cloud Run

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.app_env,
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """
    Root endpoint

    Returns:
        API information
    """
    return {
        "name": "Agent Profiler API",
        "version": "1.0.0",
        "description": "Multi-agent AI system for client data analysis",
        "status": "running",
        "documentation": "/docs" if not settings.is_production else None
    }


@app.get("/api/v1/status")
async def status(current_user: User = Depends(get_current_user)):
    """
    Get system status (authenticated)

    Args:
        current_user: Authenticated user

    Returns:
        System status information
    """
    return {
        "status": "operational",
        "user": {
            "email": current_user.email,
            "name": current_user.name
        },
        "features": {
            "csv_upload": settings.enable_csv_upload,
            "salesforce": settings.enable_salesforce_connector,
            "wealthbox": settings.enable_wealthbox_connector,
            "redtail": settings.enable_redtail_connector,
            "junxure": settings.enable_junxure_connector
        },
        "config": {
            "agent_timeout": settings.agent_timeout_seconds,
            "max_retries": settings.max_agent_retries,
            "logging_enabled": settings.enable_agent_logging
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

from fastapi import HTTPException, status as http_status
from pydantic import BaseModel
from app.auth import verify_google_token, create_access_token


class GoogleTokenRequest(BaseModel):
    """Request body for Google OAuth token"""
    token: str


class TokenResponse(BaseModel):
    """Response with access token"""
    access_token: str
    token_type: str
    user: dict


@app.post("/api/v1/auth/google", response_model=TokenResponse)
async def google_auth(request: GoogleTokenRequest):
    """
    Authenticate with Google OAuth token

    Args:
        request: Google token request

    Returns:
        JWT access token and user info
    """
    try:
        # Verify Google token
        user_info = await verify_google_token(request.token)

        # Create our JWT token
        access_token = create_access_token(
            data={
                "sub": user_info['sub'],
                "email": user_info['email'],
                "name": user_info.get('name'),
                "picture": user_info.get('picture')
            }
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "email": user_info['email'],
                "name": user_info.get('name'),
                "picture": user_info.get('picture')
            }
        )

    except Exception as e:
        logger.error("authentication_failed", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@app.get("/api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current user information

    Args:
        current_user: Authenticated user

    Returns:
        User information
    """
    return {
        "email": current_user.email,
        "user_id": current_user.user_id,
        "name": current_user.name,
        "picture": current_user.picture,
        "is_admin": current_user.is_admin
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler

    Args:
        request: Request object
        exc: Exception

    Returns:
        JSON error response
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if not settings.is_production else "An error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# IMPORT ROUTERS
# ============================================================================

from app.routers import conversations, uploads

app.include_router(conversations.router)
app.include_router(uploads.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )
