"""
Pydantic Schemas

Request/response models and data validation schemas for the API.
"""

from typing import Optional
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