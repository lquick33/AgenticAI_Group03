"""
Application Configuration

Centralized configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""

from pathlib import Path
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings are loaded from .env file automatically.
    Required settings will raise ValidationError if missing.
    """
    
    # Google Gemini API
    GOOGLE_API_KEY: str
    
    # OpenAI API (optional, for future use)
    OPENAI_API_KEY: str | None = None
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str  # Service role key for backend operations
    
    # Application Settings
    APP_NAME: str = "Lernkompanien API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True  # Enable debug mode for development
    
    # Langfuse Observability (optional)
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"  # EU region (default)
    LANGFUSE_ENABLED: bool = False  # Feature flag
    
    # Snippet Settings
    MAX_SNIPPETS_PER_PAGE: int = 3  # Maximum number of snippets allowed per page
    MULTI_SNIPPETS_ENABLED: bool = True  # Feature flag for multiple snippets per page
    
    model_config = SettingsConfigDict(
        # Try .env in current directory, then parent directory (project root)
        env_file=[
            ".env",  # backend/.env
            "../.env",  # project root/.env
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra env variables
    )


# Singleton instance
settings = Settings()

# WICHTIG: Setze Langfuse Environment Variables aus settings, BEVOR langfuse importiert wird
# get_client() liest direkt aus os.environ, nicht aus settings!
# Dies muss hier passieren, bevor endpoints.py oder observability.py langfuse importieren
if settings.LANGFUSE_ENABLED:
    if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
        # Langfuse SDK verwendet LANGFUSE_HOST für die Base URL
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
