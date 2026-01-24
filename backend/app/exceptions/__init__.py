"""
Custom exceptions for the application.
"""

from app.exceptions.quiz_exceptions import (
    QuizGenerationError,
    QuizValidationError,
    QuizStateError,
    QuizDataError,
)

__all__ = [
    "QuizGenerationError",
    "QuizValidationError",
    "QuizStateError",
    "QuizDataError",
]
