"""
FastAPI Application Entry Point

Main application initialization and configuration.
"""

import logging
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import api_router
from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logging.getLogger("python_multipart").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Lernkompanien - Adaptive Learning Assistant",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix="/api", tags=["api"])


@app.get("/health")
async def health_check():
    return JSONResponse(
        content={
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }
    )


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    logger.error("Traceback: %s", traceback.format_exc())

    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "code": "INTERNAL_ERROR",
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": "An internal error occurred",
            "code": "INTERNAL_ERROR",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
