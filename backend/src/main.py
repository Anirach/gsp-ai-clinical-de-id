"""
Main FastAPI application for Clinical Text De-Identification System.
"""
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from utils.config import get_settings, setup_logging, validate_configuration
from api.endpoints import router
from security.auth import auth_manager


# Setup logging
settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Validate configuration
    config_issues = validate_configuration(settings)
    if config_issues:
        logger.warning("Configuration issues found:")
        for issue in config_issues:
            logger.warning(f"  - {issue}")
    
    # Initialize services (if needed)
    logger.info("Services initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI application
app = FastAPI(
    title="Clinical Text De-Identification System",
    description="""
    A proof-of-concept application for de-identifying personally identifiable information (PII/PHI) 
    from Thai and English clinical text while preserving analytical utility.
    
    ## Features
    
    - **Bilingual Support**: Thai (PyThaiNLP) and English (Microsoft Presidio) text processing
    - **Comprehensive Detection**: Names, IDs, addresses, dates, phone numbers, and more
    - **Policy-Driven Transformations**: Redact, mask, generalize, date-shift, pseudonymize
    - **Deterministic Pseudonyms**: HMAC-based pseudonymization with key derivation
    - **Complete Audit Trail**: Full traceability of all detection and transformation operations
    - **Regulatory Compliance**: PDPA, HIPAA Safe Harbor, GDPR alignment
    
    ## Security
    
    - JWT-based authentication
    - Role-based access control (RBAC)
    - Encryption at rest and in transit
    - Immutable audit logs
    - Key rotation support
    
    ## Compliance Frameworks
    
    - **PDPA (Thailand)**: Personal Data Protection Act compliance
    - **HIPAA Safe Harbor**: 18 identifier categories for de-identification
    - **GDPR**: Data protection by design and privacy
    """,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Security
security = HTTPBearer()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if not settings.debug else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted host middleware (production security)
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.host, "localhost", "127.0.0.1"]
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request, call_next):
    """Add processing time header to responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Authentication endpoints
@app.post("/auth/login")
async def login(credentials: dict):
    """
    Authenticate user and return JWT token.
    
    Request body:
    ```
    {
        "username": "admin",
        "password": "admin123"
    }
    ```
    """
    username = credentials.get("username")
    password = credentials.get("password")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    user = auth_manager.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = auth_manager.create_access_token(user)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "permissions": user.permissions
        }
    }


@app.post("/auth/create-user")
async def create_user(user_data: dict):
    """
    Create new user (admin only in production).
    
    Request body:
    ```
    {
        "username": "newuser",
        "email": "user@example.com", 
        "password": "password123",
        "role": "operator"
    }
    ```
    """
    # In production, this should require admin authentication
    from models.schemas import UserRole
    
    try:
        role = UserRole(user_data["role"])
        user = auth_manager.create_user(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
            role=role
        )
        
        return {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "created": True
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(status_code=500, detail="User creation failed")


# Include API routes
app.include_router(router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with system information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Clinical Text De-Identification System",
        "docs_url": "/docs" if settings.debug else None,
        "auth_required": True,
        "supported_languages": ["thai", "english", "mixed"],
        "compliance_frameworks": ["PDPA", "HIPAA Safe Harbor", "GDPR"],
        "features": [
            "Bilingual entity detection",
            "Policy-driven transformations", 
            "Deterministic pseudonymization",
            "Complete audit trails",
            "Human review interface"
        ]
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error", 
            "message": "An unexpected error occurred"
        }
    )


def main():
    """Run the application."""
    # Development server
    if settings.debug:
        logger.info(f"Starting development server on {settings.host}:{settings.port}")
        uvicorn.run(
            "backend.src.main:app",
            host=settings.host,
            port=settings.port,
            reload=True,
            log_level=settings.log_level.lower(),
            access_log=True
        )
    else:
        # Production server
        logger.info(f"Starting production server on {settings.host}:{settings.port}")
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
            access_log=True,
            workers=1  # Single worker for simplicity
        )


if __name__ == "__main__":
    main()