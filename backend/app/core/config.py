"""
Application Configuration

Centralized configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    GOOGLE_API_KEY: str
    OPENAI_API_KEY: str | None = None

    SUPABASE_URL: str
    SUPABASE_KEY: str

    REDIS_URL: str | None = None

    APP_NAME: str = "Lernkompanien API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    BACKEND_CORS_ORIGIN_REGEX: str | None = r"https://.*\.vercel\.app$"

    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = False

    MAX_SNIPPETS_PER_PAGE: int = 3
    MULTI_SNIPPETS_ENABLED: bool = True

    GOOGLE_CLOUD_PROJECT_ID: str | None = None
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    TTS_LANGUAGE_CODE: str = "zh-CN"
    TTS_VOICE_NAME: str | None = None
    TTS_AUDIO_ENCODING: str = "MP3"
    TTS_SPEAKING_RATE: float = 1.0

    PDF_PROCESSING_DPI: int = 200

    ANKI_USE_DOCKER: bool = True
    ANKI_APP_FALLBACK_ENABLED: bool = False
    # New rollout control. Keep the legacy boolean for one migration cycle.
    TUTOR_GRAPH_DEFAULT_VERSION: Literal["legacy", "v2"] | None = None
    TUTOR_GRAPH_V2_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=[
            ".env",
            "../.env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def backend_cors_origins(self) -> list[str]:
        raw_value = self.BACKEND_CORS_ORIGINS.strip()
        if not raw_value:
            return []

        if raw_value.startswith("["):
            parsed = json.loads(raw_value)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("BACKEND_CORS_ORIGINS must be a JSON array of strings.")
            return [item.strip() for item in parsed if item.strip()]

        return [item.strip() for item in raw_value.split(",") if item.strip()]

    @property
    def resolved_tutor_graph_default_version(self) -> Literal["legacy", "v2"]:
        configured = self.TUTOR_GRAPH_DEFAULT_VERSION
        if configured in {"legacy", "v2"}:
            return configured
        return "v2" if self.TUTOR_GRAPH_V2_ENABLED else "legacy"


settings = Settings()

if settings.LANGFUSE_ENABLED:
    if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
