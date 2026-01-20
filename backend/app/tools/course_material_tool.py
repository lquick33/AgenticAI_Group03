"""
Tool for retrieving course material summary from the database.
"""

import json
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.storage import get_course_material_summary


class GetCourseMaterialSummaryInput(BaseModel):
    """Input schema for the GetCourseMaterialSummary tool."""
    course_material_id: str = Field(description="The ID of the course material (UUID)")
    user_id: str = Field(description="The user ID for authorization (UUID)")


class GetCourseMaterialSummaryTool:
    """
    Tool for retrieving the overall summary of a course material from the course_materials table.
    
    The summary contains a JSON-encoded overview of the lecture topics, concepts,
    and key themes for the entire course material. This is useful for providing
    context about the overall lecture content when starting a new study session.
    """
    
    def __init__(self):
        self.name = "get_course_material_summary"
        self.description = (
            "Retrieves the overall summary of a course material from the course_materials table. "
            "The summary contains a JSON-encoded overview of the lecture topics, concepts, and key themes "
            "for the entire course material. Use this tool when you need to understand the overall "
            "content and structure of a lecture, especially when greeting a student for the first time "
            "or providing context about what topics will be covered."
        )
    
    def _run(
        self,
        course_material_id: str,
        user_id: str
    ) -> str:
        """
        Execute the tool synchronously.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            JSON string with course material summary data
        """
        try:
            result = get_course_material_summary(
                course_material_id=course_material_id,
                user_id=user_id
            )
            
            if result is None:
                return json.dumps({
                    "error": "Summary not found or not yet generated",
                    "summary": None
                })
            
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "error": f"Failed to retrieve course material summary: {str(e)}",
                "summary": None
            })
    
    async def _arun(
        self,
        course_material_id: str,
        user_id: str
    ) -> str:
        """
        Execute the tool asynchronously.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            JSON string with course material summary data
        """
        # Service function is synchronous, but we can call it in async context
        return self._run(course_material_id, user_id)
    
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
            args_schema=GetCourseMaterialSummaryInput
        )
