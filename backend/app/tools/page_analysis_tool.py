"""
Tool for retrieving page analysis data from the database.
"""

import json
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.adapters import get_page_analysis as _get_page_analysis


class GetPageAnalysisInput(BaseModel):
    """Input schema for the GetPageAnalysis tool."""
    course_material_id: str = Field(description="The ID of the course material (UUID)")
    page_number: int = Field(description="The page number (1-indexed)")
    user_id: str = Field(description="The user ID for authorization (UUID)")


class GetPageAnalysisTool:
    """
    Tool for retrieving structured page analysis data from the page_analyses table.
    
    This tool directly imports the service function to avoid HTTP overhead
    and potential timeout issues when calling the backend from within the backend.
    """
    
    def __init__(self):
        self.name = "get_page_analysis"
        self.description = (
            "Retrieves structured analysis data for a specific page from the page_analyses table. "
            "Returns summary, key terms, exam questions, and diagram descriptions for the specified page. "
            "Use this tool when you need information about a specific lecture slide or page."
        )
    
    def _run(
        self,
        course_material_id: str,
        page_number: int,
        user_id: str
    ) -> str:
        """
        Execute the tool synchronously.
        
        Args:
            course_material_id: Course material ID
            page_number: Page number (1-indexed)
            user_id: User ID for authorization
            
        Returns:
            JSON string with page analysis data
        """
        try:
            result = _get_page_analysis().get(
                course_material_id=course_material_id,
                page_number=page_number,
                user_id=user_id
            )
            return json.dumps(result, ensure_ascii=False)
        except ValueError as e:
            return json.dumps({
                "error": str(e),
                "summary": "",
                "key_terms": [],
                "exam_questions": [],
                "diagram_description": None
            })
        except Exception as e:
            return json.dumps({
                "error": f"Failed to retrieve page analysis: {str(e)}",
                "summary": "",
                "key_terms": [],
                "exam_questions": [],
                "diagram_description": None
            })
    
    async def _arun(
        self,
        course_material_id: str,
        page_number: int,
        user_id: str
    ) -> str:
        """
        Execute the tool asynchronously.
        
        Args:
            course_material_id: Course material ID
            page_number: Page number (1-indexed)
            user_id: User ID for authorization
            
        Returns:
            JSON string with page analysis data
        """
        # Service function is synchronous, but we can call it in async context
        return self._run(course_material_id, page_number, user_id)
    
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
            args_schema=GetPageAnalysisInput
        )
