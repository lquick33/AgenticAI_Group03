"""
Application Configuration

Centralized configuration management using Pydantic Settings.
Loads environment variables from .env file.
"""

from pathlib import Path
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
    DEBUG: bool = False
    
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
