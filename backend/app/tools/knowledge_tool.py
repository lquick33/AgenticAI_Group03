"""
Knowledge Level Tool for Agent Integration

Provides LangChain-compatible tool for querying user knowledge levels
based on Anki study data, organized by course and lecture.
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from ..services.anki import KnowledgeService, AnkiConnectionError
from app.core.adapters import get_course as _get_course

logger = logging.getLogger(__name__)


class GetCourseKnowledgeInput(BaseModel):
    """Input schema for get_course_knowledge tool."""
    course_id: str = Field(
        description="UUID of the course to get knowledge levels for"
    )
    user_id: str = Field(
        description="UUID of the user"
    )


class GetCourseKnowledgeTool:
    """
    Tool for getting knowledge levels for a course with per-lecture breakdown.
    
    This tool allows the agent to understand the user's mastery of different
    lecture topics based on their Anki study data.
    """
    
    name: str = "get_course_knowledge"
    description: str = """Get the user's knowledge level for each lecture in a course.
    
Returns mastery scores (0.0-1.0) based on Anki flashcard study data:
- Course-level overall mastery
- Per-lecture mastery breakdown
- Status labels: mastered, progressing, needs_review, not_started
- Identifies weakest and strongest lectures
- Provides study recommendations

Use this tool to:
- Understand which topics the user has mastered
- Identify areas that need more attention before an exam
- Personalize tutoring based on knowledge gaps
- Decide whether to review or move to new material"""

    def __init__(self):
        self._knowledge_service = None
    
    @property
    def knowledge_service(self) -> KnowledgeService:
        """Lazy initialization of knowledge service."""
        if self._knowledge_service is None:
            self._knowledge_service = KnowledgeService()
        return self._knowledge_service
    
    def invoke(self, course_id: str, user_id: str) -> dict:
        """
        Get knowledge levels for a course.
        
        Args:
            course_id: UUID of the course
            user_id: UUID of the user
            
        Returns:
            Dictionary with course and per-lecture mastery scores
        """
        # Get course with materials
        course = _get_course().get_with_materials(user_id, course_id)
        
        if not course:
            return {
                "status": "error",
                "error": "Course not found or access denied",
                "course_id": course_id,
            }
        
        course_title = course.get("title", "Unknown Course")
        materials = course.get("materials", [])
        
        if not materials:
            return {
                "status": "success",
                "course": {
                    "id": course_id,
                    "title": course_title,
                    "overall_mastery": 0.0,
                    "total_cards": 0,
                },
                "lectures": [],
                "message": f"No materials found for '{course_title}'. Upload lecture PDFs first."
            }
        
        try:
            result = self.knowledge_service.get_course_knowledge(
                course_id=course_id,
                course_title=course_title,
                materials=materials,
            )
            
            return {
                "status": result.status,
                "course": {
                    "id": result.course_id,
                    "title": result.course_title,
                    "overall_mastery": result.overall_mastery,
                    "total_cards": result.total_cards,
                },
                "lectures": [
                    {
                        "name": lecture.name,
                        "mastery_score": lecture.mastery_score,
                        "total_cards": lecture.total_cards,
                        "status": lecture.status,
                    }
                    for lecture in result.lectures
                ],
                "weakest_lecture": result.weakest_lecture,
                "strongest_lecture": result.strongest_lecture,
                "recommendations": result.recommendations,
            }
        except AnkiConnectionError as e:
            return {
                "status": "error",
                "error": f"Could not connect to Anki: {e}",
                "message": "Make sure Anki is running with the AnkiConnect add-on installed."
            }
        except Exception as e:
            logger.error(f"Error getting course knowledge: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
    
    def to_langchain_tool(self):
        """Convert to a LangChain-compatible tool."""
        @tool(args_schema=GetCourseKnowledgeInput)
        def get_course_knowledge(course_id: str, user_id: str) -> str:
            """Get the user's knowledge level for each lecture in a course.
            
            Returns mastery scores based on Anki study data with per-lecture breakdown.
            Use this to understand which topics need more attention.
            
            Args:
                course_id: UUID of the course
                user_id: UUID of the user
            """
            result = self.invoke(course_id, user_id)
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        return get_course_knowledge


# Convenience function for direct use
def get_course_knowledge_tool() -> GetCourseKnowledgeTool:
    """Get an instance of the course knowledge tool."""
    return GetCourseKnowledgeTool()
