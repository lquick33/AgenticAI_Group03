"""
Tool for retrieving all user's courses and their materials.

Used by the Quick Chat agent to understand what courses are available.
"""

import json
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.adapters import get_course as _get_course


class GetUserCoursesInput(BaseModel):
    """Input schema for the GetUserCourses tool."""
    user_id: str = Field(description="The user ID for authorization (UUID)")


class GetUserCoursesTool:
    """
    Tool for retrieving all courses and materials for a user.
    
    Returns a structured list of courses with their lecture materials,
    useful for showing the user what's available to study.
    """
    
    def __init__(self):
        self.name = "get_user_courses"
        self.description = (
            "Retrieves ALL courses and lecture materials for the user. "
            "Returns a list of courses, each with their associated lecture materials "
            "(PDFs, presentations, etc.). Use this tool when you need to show the user "
            "what courses and materials they have available, or when you need to understand "
            "the overall structure of their study materials."
        )
    
    def _run(self, user_id: str) -> str:
        """
        Execute the courses retrieval.
        
        Args:
            user_id: User ID for authorization
            
        Returns:
            JSON string with courses and materials
        """
        try:
            courses = _get_course().get_all_with_materials(user_id=user_id)
            
            if not courses:
                return json.dumps({
                    "found": False,
                    "message": "You don't have any courses yet. Upload some lecture materials to get started!",
                    "courses": []
                }, ensure_ascii=False)
            
            # Calculate totals
            total_materials = sum(len(c.get("materials", [])) for c in courses)
            total_pages = sum(
                sum(m.get("page_count", 0) for m in c.get("materials", []))
                for c in courses
            )
            
            return json.dumps({
                "found": True,
                "message": f"You have {len(courses)} course(s) with {total_materials} lecture material(s) ({total_pages} total pages).",
                "courses": courses,
                "summary": {
                    "total_courses": len(courses),
                    "total_materials": total_materials,
                    "total_pages": total_pages
                }
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get courses: {str(e)}",
                "found": False,
                "courses": []
            })
    
    async def _arun(self, user_id: str) -> str:
        """
        Execute the courses retrieval asynchronously.
        """
        return self._run(user_id)
    
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
            args_schema=GetUserCoursesInput
        )
