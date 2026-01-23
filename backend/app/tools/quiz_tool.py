"""
Tool for creating quizzes from lecture material.

This tool is used by the Tutor Agent to generate quizzes when a subtopic is completed.
"""

import json
import logging
from typing import Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agents.quiz.quiz_generator_agent import QuizGeneratorAgent
from app.services.quiz_service import save_quiz
from app.services.analyzer import get_gemini_model

logger = logging.getLogger(__name__)


class CreateQuizInput(BaseModel):
    """Input schema for the CreateQuiz tool."""
    start_page: int = Field(..., ge=1, description="Starting page number (1-indexed, inclusive)")
    end_page: int = Field(..., ge=1, description="Ending page number (1-indexed, inclusive)")
    course_material_id: str = Field(..., description="Course material ID (UUID)")
    user_id: str = Field(..., description="User ID (UUID)")


class CreateQuizTool:
    """
    Tool for creating quizzes for completed subtopics.
    
    This tool is called by the Tutor Agent when it detects that a subtopic
    has been fully covered. It generates a quiz using the QuizGeneratorAgent
    and saves it to the database.
    
    The tool returns the quiz ID and quiz data as JSON, which can be
    included in the Tutor's response to the frontend.
    """
    
    def __init__(self, quiz_agent: Optional[QuizGeneratorAgent] = None):
        """
        Initialize CreateQuizTool.
        
        Args:
            quiz_agent: Optional QuizGeneratorAgent instance.
                       If None, creates a new one with default settings.
        """
        self.name = "create_quiz"
        self.description = (
            "Erstellt ein Quiz für ein abgeschlossenes Unterthema. "
            "Das Quiz wird automatisch generiert und enthält 3-5 Verständnisfragen "
            "(bei komplexen Themen können es auch mehr sein, max. 8). "
            "Parameter: start_page (Startseite des Themas), end_page (Endseite des Themas). "
            "Das Tool gibt die Quiz-ID und Quiz-Daten zurück, die im Chat angezeigt werden können."
        )
        
        # Initialize quiz agent if not provided
        if quiz_agent is None:
            llm = get_gemini_model()
            self.quiz_agent = QuizGeneratorAgent(llm=llm)
        else:
            self.quiz_agent = quiz_agent
    
    def _run(
        self,
        start_page: int,
        end_page: int,
        course_material_id: str,
        user_id: str
    ) -> str:
        """
        Execute the tool synchronously.
        
        Args:
            start_page: Starting page number (1-indexed, inclusive)
            end_page: Ending page number (1-indexed, inclusive)
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            JSON string with quiz_id and quiz_data
        """
        try:
            # Validate page range
            if start_page > end_page:
                return json.dumps({
                    "error": f"start_page ({start_page}) muss <= end_page ({end_page}) sein",
                    "quiz_id": None,
                    "quiz_data": None
                }, ensure_ascii=False)
            
            # Generate quiz using QuizGeneratorAgent
            logger.info(
                f"Generating quiz for pages {start_page}-{end_page} "
                f"(material: {course_material_id}, user: {user_id})"
            )
            
            quiz_data = self.quiz_agent.generate_quiz(
                start_page=start_page,
                end_page=end_page,
                course_material_id=course_material_id,
                user_id=user_id
            )
            
            # Save quiz to database
            quiz_id = save_quiz(
                quiz_data=quiz_data,
                course_material_id=course_material_id,
                user_id=user_id,
                start_page=start_page,
                end_page=end_page,
                topic_name=quiz_data.topic
            )
            
            # Return quiz ID and data as JSON
            result = {
                "quiz_id": quiz_id,
                "quiz_data": quiz_data.model_dump(),
                "topic": quiz_data.topic,
                "question_count": len(quiz_data.questions),
                "start_page": start_page,
                "end_page": end_page
            }
            
            logger.info(f"Quiz created successfully: {quiz_id} ({len(quiz_data.questions)} questions)")
            
            return json.dumps(result, ensure_ascii=False)
        
        except ValueError as e:
            logger.error(f"Validation error in create_quiz: {str(e)}")
            return json.dumps({
                "error": str(e),
                "quiz_id": None,
                "quiz_data": None
            }, ensure_ascii=False)
        
        except Exception as e:
            logger.error(f"Failed to create quiz: {str(e)}", exc_info=True)
            return json.dumps({
                "error": f"Fehler bei Quiz-Erstellung: {str(e)}",
                "quiz_id": None,
                "quiz_data": None
            }, ensure_ascii=False)
    
    async def _arun(
        self,
        start_page: int,
        end_page: int,
        course_material_id: str,
        user_id: str
    ) -> str:
        """
        Execute the tool asynchronously.
        
        Args:
            start_page: Starting page number (1-indexed, inclusive)
            end_page: Ending page number (1-indexed, inclusive)
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            JSON string with quiz_id and quiz_data
        """
        # For now, use sync implementation
        # QuizGeneratorAgent.generate_quiz is sync, so we can call it directly
        return self._run(start_page, end_page, course_material_id, user_id)
    
    def to_langchain_tool(self) -> StructuredTool:
        """
        Convert this tool to a LangChain StructuredTool.
        
        Returns:
            LangChain StructuredTool instance
        """
        return StructuredTool(
            name=self.name,
            description=self.description,
            func=self._run,
            args_schema=CreateQuizInput
        )
