"""
Celery configuration for background task processing.

This file initializes the Celery application and configures it to use Redis
as the message broker and backend. It is used to process long-running tasks
like PDF processing and flashcard generation outside of the main FastAPI requests.
"""

from pathlib import Path
import os
import ssl
from urllib.parse import urlparse, urlunparse

from celery import Celery
from dotenv import load_dotenv


def _load_env_files() -> None:
    """
    Load .env values for standalone worker runs.

    Celery workers can be started directly via CLI, so we load both
    backend/.env and project-root/.env explicitly.
    """
    backend_dir = Path(__file__).resolve().parents[2]  # .../backend
    for env_file in (backend_dir / ".env", backend_dir.parent / ".env"):
        if env_file.exists():
            load_dotenv(env_file, override=False)


_load_env_files()


def _normalize_redis_url(raw_url: str) -> str:
    """
    Normalize Redis URL for Celery/Kombu compatibility.

    - Upstash requires TLS (`rediss://`), so upgrade scheme automatically.
    - Ensure a Redis DB path exists (`/0`) to avoid ambiguous `//` URLs.
    """
    url = raw_url.strip().strip('"').strip("'")
    parsed = urlparse(url)

    scheme = parsed.scheme
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or "/0"

    if path in ("", "/"):
        path = "/0"

    if hostname.endswith("upstash.io") and scheme == "redis":
        scheme = "rediss"

    return urlunparse(
        (scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
    )

# Create the celery application instance
# The main module name should be "app.core.celery_app" or whatever the import path is
celery_app = Celery("studybuddy_worker")

# Define configuration parameters
# We use the REDIS_URL from environment variables, defaulting to local Redis if not present
raw_redis_url = os.environ.get("REDIS_URL")
redis_url = _normalize_redis_url(raw_redis_url) if raw_redis_url else "redis://localhost:6379/0"

is_secure_redis = redis_url.startswith("rediss://")
ssl_options = {"ssl_cert_reqs": ssl.CERT_REQUIRED} if is_secure_redis else None

celery_app.conf.update(
    broker_url=redis_url,
    result_backend=redis_url,
    broker_use_ssl=ssl_options,
    redis_backend_use_ssl=ssl_options,
    imports=("app.services.pdf_processor",),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Rate limit and failure settings can be added here
)

# Optional: Auto-discover tasks in specific modules
# celery_app.autodiscover_tasks(["app.services.pdf_processor", "app.services.flashcard_task_service"])

if __name__ == '__main__':
    celery_app.start()
