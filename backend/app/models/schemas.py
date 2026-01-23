"""
Pydantic Schemas

Request/response models and data validation schemas for the API.
"""

from typing import Optional, Literal, Dict, List
from pydantic import BaseModel, Field


class SlideAnalysis(BaseModel):
    """
    Structured analysis result for a lecture slide.
    
    This model defines the expected output structure from the multimodal LLM analysis.
    Used for type-safe structured output with LangChain's with_structured_output().
    """
    
    summary: str = Field(
        ...,
        description="Eine prägnante Zusammenfassung des Folieninhalts"
    )
    
    key_terms: list[str] = Field(
        ...,
        description="Die wichtigsten Fachbegriffe auf der Folie"
    )
    
    exam_questions: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Genau 2 mögliche Prüfungsfragen, die sich aus dem Inhalt ergeben"
    )
    
    diagram_description: str = Field(
        ...,
        description="Beschreibung visueller Elemente (Diagramme, Charts, Grafiken). Falls nur Text vorhanden, dann 'Kein Diagramm'"
    )


class PageAnalysisResponse(BaseModel):
    """Response model for a single page analysis."""
    
    page_number: int
    analysis: SlideAnalysis
    status: str = "completed"


class UploadResponse(BaseModel):
    """Response model for PDF upload endpoint."""
    
    message: str
    course_material_id: Optional[str] = None
    page_count: int
    pages_analyzed: int
    status: str  # "processing", "completed", "error"
    error_message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    
    error: str
    code: str
    details: Optional[dict] = None


class CourseResponse(BaseModel):
    """Response model for course data."""
    
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    exam_date: Optional[str] = None  # ISO date string (YYYY-MM-DD)
    color_code: Optional[str] = None
    created_at: str
    updated_at: str


class CourseUpdateRequest(BaseModel):
    """Request model for updating course data."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    exam_date: Optional[str] = None  # ISO date string (YYYY-MM-DD) or null
    color_code: Optional[str] = None


class ChatInitiateRequest(BaseModel):
    """Request model for initiating a chat session."""
    
    material_id: str = Field(..., description="Course material ID (UUID)")
    page_number: int = Field(..., description="Current page number (1-indexed)")
    user_id: str = Field(..., description="User ID (UUID)")
    is_initial_open: bool = Field(
        default=False,
        description="Whether this is the initial opening of the study reader (true) or just a page change (false)"
    )


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    
    material_id: str = Field(..., description="Course material ID (UUID)")
    message: str = Field(..., description="User message content")
    user_id: str = Field(..., description="User ID (UUID)")


class PageAnalysisQuery(BaseModel):
    """Query model for retrieving page analysis."""
    
    course_material_id: str = Field(..., description="Course material ID (UUID)")
    page_number: int = Field(..., description="Page number (1-indexed)")
    user_id: str = Field(..., description="User ID (UUID)")


class PageAnalysisDataResponse(BaseModel):
    """Response model for page analysis data."""
    
    summary: str
    key_terms: list[str]
    exam_questions: list[str]
    diagram_description: Optional[str] = None
    raw_analysis: Optional[dict] = None


class PageSkipDecision(BaseModel):
    """Decision model for whether to skip a page (intro/title/table of contents)."""
    
    skip: bool = Field(..., description="True if this page should be skipped (intro/title/TOC), False otherwise")
    reason: str = Field(..., description="Brief reason for the decision")


class Flashcard(BaseModel):
    """Model for a single flashcard."""
    
    front: str = Field(..., description="Front side of the flashcard (question or term)")
    back: str = Field(..., description="Back side of the flashcard (answer or definition)")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization (e.g., course_id, page_number, topic)")


class FlashcardGenerationResult(BaseModel):
    """Result model for flashcard generation for a single page."""
    
    cards: list[Flashcard] = Field(..., description="List of flashcards generated for this page")


class FlashcardTaskResponse(BaseModel):
    """Response model for flashcard generation task creation."""
    
    task_id: str = Field(..., description="Task ID for tracking progress")
    status: str = Field(..., description="Current task status")
    message: str = Field(..., description="Human-readable status message")


class FlashcardTaskStatusResponse(BaseModel):
    """Response model for flashcard generation task status."""
    
    task_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    total_pages: int
    processed_pages: int
    cards_generated: int
    error_message: Optional[str] = None
    filename: Optional[str] = None
    created_at: float
    completed_at: Optional[float] = None


class MaterialUpdateRequest(BaseModel):
    """Request model for updating course material data."""
    
    file_name: Optional[str] = Field(None, description="New filename for the material")


class MaterialResponse(BaseModel):
    """Response model for course material data."""
    
    id: str
    course_id: str
    user_id: str
    file_name: str
    file_path: str
    file_type: str
    page_count: int
    processing_status: str
    error_message: Optional[str] = None
    created_at: str
    summary: Optional[str] = None


# Quiz-related models

class QuizQuestion(BaseModel):
    """Model for a single quiz question."""
    
    id: str = Field(..., description="Unique question identifier (e.g., 'q1', 'q2')")
    question: str = Field(..., description="The question text")
    options: Dict[str, str] = Field(
        ...,
        description="Answer options as a dictionary with keys A, B, C, D",
        min_length=4,
        max_length=4
    )
    correct_answer: Literal["A", "B", "C", "D"] = Field(
        ...,
        description="The correct answer option (A, B, C, or D)"
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        ...,
        description="Question difficulty level"
    )
    explanation: str = Field(
        ...,
        description="Explanation of the correct answer (shown after user answers)"
    )


class QuizData(BaseModel):
    """Model for complete quiz data structure."""
    
    topic: str = Field(..., description="Topic name for this quiz")
    questions: List[QuizQuestion] = Field(
        ...,
        description="List of quiz questions",
        min_length=3,
        max_length=8
    )
    metadata: Dict[str, int] = Field(
        default_factory=dict,
        description="Metadata about question distribution (e.g., {'easy_count': 2, 'medium_count': 1, 'hard_count': 1})"
    )


class QuizCreate(BaseModel):
    """Input model for creating a quiz."""
    
    start_page: int = Field(..., ge=1, description="Starting page number (1-indexed)")
    end_page: int = Field(..., ge=1, description="Ending page number (1-indexed)")
    course_material_id: str = Field(..., description="Course material ID (UUID)")
    user_id: str = Field(..., description="User ID (UUID)")


class QuizSubmit(BaseModel):
    """Input model for submitting quiz answers."""
    
    quiz_id: str = Field(..., description="Quiz ID (UUID)")
    answers: Dict[str, str] = Field(
        ...,
        description="User answers as a dictionary mapping question_id to answer (A, B, C, or D)"
    )
    user_id: str = Field(..., description="User ID (UUID)")


class QuestionResult(BaseModel):
    """Model for individual question result."""
    
    question_id: str
    user_answer: Literal["A", "B", "C", "D"]
    correct_answer: Literal["A", "B", "C", "D"]
    correct: bool
    explanation: Optional[str] = None


class QuizResult(BaseModel):
    """Response model for quiz submission results."""
    
    quiz_id: str
    score: float = Field(..., ge=0.0, le=1.0, description="Score from 0.0 to 1.0")
    correct_count: int
    total_questions: int
    question_results: List[QuestionResult]
    completed_at: str
    tutor_feedback: Optional[str] = Field(None, description="Tutor feedback message based on quiz results")


class QuizResponse(BaseModel):
    """Response model for quiz data retrieval."""
    
    id: str
    course_material_id: str
    user_id: str
    topic_name: str
    start_page: int
    end_page: int
    quiz_data: QuizData
    created_at: str