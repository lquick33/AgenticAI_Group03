"""Minimal backend smoke test for CI and local verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy")
os.environ.setdefault("DEBUG", "false")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "healthy", payload
    print("[PASS] Backend smoke test succeeded")


if __name__ == "__main__":
    main()
