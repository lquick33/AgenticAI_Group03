"""
Custom exceptions for quiz generation and handling.

These exceptions provide structured error handling for the quiz feature,
replacing ad-hoc string matching and error messages with proper exception types.
"""

from typing import Optional, Dict, Any


class QuizGenerationError(Exception):
    """
    Base exception for quiz generation errors.
    
    This is the parent class for all quiz-related exceptions.
    Use this for general quiz generation failures.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize QuizGenerationError.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class QuizValidationError(QuizGenerationError):
    """
    Exception raised when quiz data validation fails.
    
    Use this when quiz data doesn't meet requirements (e.g., wrong number
    of questions, missing fields, invalid difficulty distribution).
    """
    
    def __init__(
        self,
        message: str,
        validation_errors: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize QuizValidationError.
        
        Args:
            message: Human-readable error message
            validation_errors: Dictionary mapping field names to validation errors
            details: Optional dictionary with additional error details
        """
        super().__init__(message, details)
        self.validation_errors = validation_errors or {}
    
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.validation_errors:
            errors_str = ", ".join(f"{k}: {v}" for k, v in self.validation_errors.items())
            return f"{base_msg} (Validation errors: {errors_str})"
        return base_msg


class QuizStateError(QuizGenerationError):
    """
    Exception raised when quiz state management fails.
    
    Use this when state is missing, invalid, or inconsistent (e.g., missing
    page_analyses, invalid state transitions, state corruption).
    """
    
    def __init__(
        self,
        message: str,
        state_info: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize QuizStateError.
        
        Args:
            message: Human-readable error message
            state_info: Dictionary with state information (keys present, values, etc.)
            details: Optional dictionary with additional error details
        """
        super().__init__(message, details)
        self.state_info = state_info or {}
    
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.state_info:
            state_str = ", ".join(f"{k}={v}" for k, v in self.state_info.items())
            return f"{base_msg} (State info: {state_str})"
        return base_msg


class QuizDataError(QuizGenerationError):
    """
    Exception raised when quiz data structure is invalid or corrupted.
    
    Use this when quiz data cannot be parsed, is malformed, or has structural
    issues (e.g., invalid JSON, missing required fields, type mismatches).
    """
    
    def __init__(
        self,
        message: str,
        data_info: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize QuizDataError.
        
        Args:
            message: Human-readable error message
            data_info: Dictionary with data information (type, keys, etc.)
            details: Optional dictionary with additional error details
        """
        super().__init__(message, details)
        self.data_info = data_info or {}
    
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.data_info:
            data_str = ", ".join(f"{k}={v}" for k, v in self.data_info.items())
            return f"{base_msg} (Data info: {data_str})"
        return base_msg
