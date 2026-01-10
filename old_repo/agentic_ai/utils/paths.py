"""
Utility for defining and accessing key paths within the project.

This module centralizes path definitions to ensure consistent referencing
of project directories, especially the root directory.
"""

from pathlib import Path

# Defines the absolute path to the project root directory.
# It navigates up two levels from the current file's location.
# __file__ is agentic_ai/utils/paths.py
# .parents[0] is agentic_ai/utils
# .parents[1] is agentic_ai
# .parents[2] is the project root (agentic_artificial_intelligence)
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"; DATA_DIR.mkdir(exist_ok=True)
EXAMPLE_MEMORY_DIR = DATA_DIR / "example_memory"; EXAMPLE_MEMORY_DIR.mkdir(exist_ok=True)

ENV = ROOT / ".env"