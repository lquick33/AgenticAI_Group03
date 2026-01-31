"""
Anki Integration Service

Provides AnkiConnect API wrapper for:
- Reading study statistics
- Creating flashcards
- Syncing with AnkiWeb
- Managing the headless Anki Docker container
"""

from .client import AnkiClient, AnkiError

__all__ = ["AnkiClient", "AnkiError"]
