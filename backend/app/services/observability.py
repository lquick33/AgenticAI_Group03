"""
Langfuse Observability Service

Provides centralized token tracking and observability for LLM calls.
Uses Langfuse SDK v3+ with OpenTelemetry-based tracing.

The CallbackHandler automatically tracks:
- Token Usage (input/output tokens)
- Model Parameters
- Input/Output Messages
- Latency
- Errors
"""

from typing import Optional, Dict, Any
import logging
import os
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_langfuse_client():
    """
    Get Langfuse client instance using the recommended get_client() method.
    
    Returns:
        Langfuse client if configured, None otherwise
        
    Note:
        Uses environment variables automatically:
        - LANGFUSE_PUBLIC_KEY
        - LANGFUSE_SECRET_KEY
        - LANGFUSE_BASE_URL (optional)
        
        get_client() manages the singleton automatically.
    """
    if not settings.LANGFUSE_ENABLED:
        logger.info("🔴 Langfuse: DISABLED (LANGFUSE_ENABLED=False)")
        return None
    
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning("🔴 Langfuse: ENABLED but missing credentials (PUBLIC_KEY or SECRET_KEY)")
        return None
    
    try:
        # WICHTIG: get_client() liest direkt aus os.environ, nicht aus settings!
        # Daher müssen wir die Werte aus settings in os.environ setzen
        if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
            os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
            # Langfuse SDK verwendet LANGFUSE_HOST für die Base URL
            os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
        
        # Versuche, den Singleton zurückzusetzen, falls er bereits als disabled initialisiert wurde
        # Dies ist nötig, falls get_client() vor dem Setzen der env vars aufgerufen wurde
        try:
            from langfuse.resource_manager import LangfuseResourceManager
            # Reset nur wenn env vars jetzt gesetzt sind, aber vorher nicht waren
            if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
                logger.info("🟡 Langfuse: Resetting singleton to ensure fresh initialization...")
                LangfuseResourceManager.reset()
                logger.info("🟢 Langfuse: Singleton reset completed")
        except (ImportError, AttributeError) as e:
            # LangfuseResourceManager könnte in manchen Versionen nicht verfügbar sein
            logger.debug(f"LangfuseResourceManager not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to reset Langfuse singleton: {e}")
        
        # get_client() ist die empfohlene Methode (SDK v3+)
        # Verwendet automatisch Environment Variables und verwaltet Singleton
        logger.info(f"🟡 Langfuse: Initializing client (Base URL: {settings.LANGFUSE_BASE_URL})")
        langfuse = get_client()
        
        logger.info(f"🟢 Langfuse: Client initialized successfully (Base URL: {settings.LANGFUSE_BASE_URL})")
        
        # Optional: Verify connection
        if hasattr(langfuse, 'auth_check'):
            logger.info("🟡 Langfuse: Checking authentication...")
            auth_result = langfuse.auth_check()
            if not auth_result:
                logger.warning("🔴 Langfuse: auth_check FAILED - credentials may be invalid")
                return None
            logger.info("🟢 Langfuse: Authentication check PASSED")
        
        return langfuse
    except Exception as e:
        # Graceful degradation: Wenn Langfuse nicht verfügbar ist,
        # sollte die App weiterhin funktionieren
        logger.error(f"🔴 Langfuse: Failed to initialize client: {e}", exc_info=True)
        return None


def create_callback_handler() -> Optional[CallbackHandler]:
    """
    Create Langfuse CallbackHandler for LangChain integration.
    
    Der CallbackHandler trackt automatisch:
    - Token Usage (input/output tokens) aus response_metadata
    - Model Parameters
    - Input/Output Messages
    - Latency
    - Errors
    
    Returns:
        CallbackHandler if Langfuse enabled, None otherwise
        
    Note:
        In Langfuse SDK v3+, CallbackHandler verwendet automatisch get_client(),
        der die Environment Variables (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, etc.) liest.
        
        WICHTIG: user_id, session_id und metadata müssen via LangChain config metadata übergeben werden:
        
        ```python
        config = {
            "callbacks": [callback_handler],
            "metadata": {
                "langfuse_user_id": "user-123",
                "langfuse_session_id": "session-456",
                # weitere metadata...
            }
        }
        ```
    """
    if not settings.LANGFUSE_ENABLED:
        logger.debug("🔴 Langfuse: CallbackHandler not created (disabled)")
        return None
    
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.debug("🔴 Langfuse: CallbackHandler not created (missing credentials)")
        return None
    
    try:
        # In v3+, CallbackHandler verwendet automatisch get_client() der Environment Variables liest
        # Keine Constructor-Parameter mehr für public_key, secret_key, host
        # user_id, session_id, metadata werden via LangChain config metadata übergeben
        logger.info("🟡 Langfuse: Creating CallbackHandler...")
        handler = CallbackHandler()
        
        logger.info("🟢 Langfuse: CallbackHandler created successfully")
        return handler
    except Exception as e:
        logger.error(f"🔴 Langfuse: Failed to create CallbackHandler: {e}", exc_info=True)
        return None


def extract_token_usage(response) -> Dict[str, int]:
    """
    Extract token usage from LLM response (optional, für Debugging).
    
    Hinweis: Der CallbackHandler extrahiert Token-Usage automatisch.
    Diese Funktion ist nur für manuelle Extraktion oder Debugging nötig.
    
    Handles different response formats (Gemini, OpenAI, etc.)
    
    Args:
        response: LLM response object (LangChain AIMessage)
        
    Returns:
        Dict with input_tokens and output_tokens
    """
    usage = {"input_tokens": 0, "output_tokens": 0}
    
    # Try to get usage from response_metadata (LangChain standard)
    if hasattr(response, "response_metadata"):
        metadata = response.response_metadata or {}
        usage_meta = metadata.get("usage_metadata", {})
        
        # Gemini format
        if "input_token_count" in usage_meta:
            usage["input_tokens"] = usage_meta.get("input_token_count", 0)
        if "output_token_count" in usage_meta:
            usage["output_tokens"] = usage_meta.get("output_token_count", 0)
        
        # OpenAI format
        if "prompt_tokens" in usage_meta:
            usage["input_tokens"] = usage_meta.get("prompt_tokens", 0)
        if "completion_tokens" in usage_meta:
            usage["output_tokens"] = usage_meta.get("completion_tokens", 0)
    
    return usage


def flush_langfuse():
    """
    Flush pending Langfuse events.
    
    Wichtig für short-lived processes (z.B. Serverless Functions).
    In lang laufenden Services ist flush() optional, da Langfuse
    automatisch im Hintergrund sendet.
    """
    langfuse = get_langfuse_client()
    if langfuse:
        try:
            logger.info("🟡 Langfuse: Flushing pending events...")
            langfuse.flush()
            logger.info("🟢 Langfuse: Events flushed successfully - data sent to Langfuse")
        except Exception as e:
            # Graceful degradation: Fehler beim Flush sollten
            # die App nicht zum Absturz bringen
            logger.warning(f"🔴 Langfuse: Failed to flush events: {e}")


def shutdown_langfuse():
    """
    Gracefully shutdown Langfuse client.
    
    Sollte am Ende der App aufgerufen werden (z.B. bei Shutdown-Signal).
    Führt flush() aus und beendet Background-Threads.
    """
    langfuse = get_langfuse_client()
    if langfuse:
        try:
            logger.info("🟡 Langfuse: Shutting down client...")
            langfuse.shutdown()
            logger.info("🟢 Langfuse: Client shut down successfully")
        except Exception as e:
            logger.warning(f"🔴 Langfuse: Error during shutdown: {e}")
