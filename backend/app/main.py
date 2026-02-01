"""
FastAPI Application Entry Point

Main application initialization and configuration.
"""

import logging
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.endpoints import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from multipart library
logging.getLogger("python_multipart").setLevel(logging.WARNING)

# Reduce noise from urllib3 (used by Langfuse SDK for HTTP requests)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

# Reduce noise from hpack (HTTP/2, used by Supabase/httpx)
logging.getLogger("hpack").setLevel(logging.WARNING)

# Reduce noise from httpcore (used by httpx/Supabase: http2 + http11)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Lernkompanien - Adaptive Learning Assistant",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",
        "https://*.vercel.app",  # Vercel deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # Allow frontend to read download filenames
)

# Include API router
app.include_router(api_router, prefix="/api", tags=["api"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        JSON response with status
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION
        }
    )


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        Welcome message
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "code": "VALIDATION_ERROR"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    # Always log the full error
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    if settings.DEBUG:
        # In debug mode, return full error details
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "code": "INTERNAL_ERROR",
                "type": type(exc).__name__,
                "traceback": traceback.format_exc() if settings.DEBUG else None
            }
        )
    else:
        # In production, return generic error
        return JSONResponse(
            status_code=500,
            content={
                "error": "An internal error occurred",
                "code": "INTERNAL_ERROR"
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
