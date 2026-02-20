"""
Tool for extracting a visual snapshot of a PDF page.
"""

import json
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.adapters import get_file_storage as _get_file_storage
from app.services.pdf_processor import extract_page_image


class GetPageImageInput(BaseModel):
    """Input schema for the GetPageImage tool."""
    course_material_id: str = Field(description="The ID of the course material (UUID)")
    page_number: int = Field(description="The page number to retrieve (1-indexed)")
    user_id: str = Field(description="The user ID for authorization (UUID)")


class GetPageImageTool:
    """
    Tool for retrieving a visual snapshot of a specific page from a course material PDF.
    
    This tool extracts the requested page as an image and returns it as a base64 Data URI.
    This allows the agent to visually inspect the slide content, which is useful for:
    - Analyzing complex diagrams or charts that text extraction might miss
    - Resolving discrepancies between user perception and database text
    - Double-checking specific visual details on a slide
    """
    
    def __init__(self):
        self.name = "get_page_image"
        self.description = (
            "Retrieves a visual snapshot of a specific page from the course material. "
            "Use this tool when you need to visually inspect a slide, for example when "
            "there are complex diagrams, charts, or when you suspect the text analysis "
            "might be incomplete or incorrect. Returns the image as a base64 string."
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
            JSON string with status and image_data (base64 Data URI)
        """
        client = get_supabase_client()
        
        try:
            # 1. Get file_path from course_materials table
            response = client.table("course_materials").select(
                "file_path, user_id"
            ).eq("id", course_material_id).single().execute()
            
            if not response.data:
                return json.dumps({
                    "error": f"Course material not found: {course_material_id}",
                    "status": "error"
                })
            
            material_data = response.data
            file_path = material_data.get("file_path")
            owner_id = material_data.get("user_id")
            
            # Verify ownership
            if owner_id != user_id:
                return json.dumps({
                    "error": "Access denied",
                    "status": "error"
                })
            
            if not file_path:
                return json.dumps({
                    "error": "File path not found for this material",
                    "status": "error"
                })
            
            # 2. Download PDF file
            pdf_bytes = _get_file_storage().download(file_path)
            
            # 3. Extract page image
            image_data = extract_page_image(pdf_bytes, page_number)
            
            return json.dumps({
                "status": "success",
                "image_data": image_data,
                "page_number": page_number,
                "message": f"Successfully retrieved image for page {page_number}"
            })
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to retrieve page image: {str(e)}",
                "status": "error"
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
            JSON string with status and image_data
        """
        # Service function calls are synchronous (requests library), 
        # but we can wrap them if needed. For now, calling _run is sufficient.
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
            coroutine=self._arun,
            args_schema=GetPageImageInput
        )
