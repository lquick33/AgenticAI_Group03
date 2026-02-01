"""
Tool for searching topics across all user's courses and materials.

Used by the Quick Chat agent to find where a topic is discussed in lectures.
"""

import json
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.storage import search_page_analyses


class SearchTopicInput(BaseModel):
    """Input schema for the SearchTopic tool."""
    query: str = Field(description="The topic or concept to search for")
    user_id: str = Field(description="The user ID for authorization (UUID)")
    language: str = Field(
        default="auto",
        description="Language for search: 'de' for German, 'en' for English, 'auto' for both"
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return"
    )


class SearchTopicTool:
    """
    Tool for searching topics across all courses and lecture materials.
    
    Uses full-text search to find pages where a topic is discussed,
    returning context about the course, material, and page location.
    """
    
    def __init__(self):
        self.name = "search_topic"
        self.description = (
            "Searches for a topic or concept across ALL of the user's courses and lecture materials. "
            "Returns a list of pages where the topic is discussed, including the course name, "
            "lecture/material name, page number, and a summary of the content. "
            "Use this tool when the user asks about a topic and you need to find where it's covered "
            "in their lecture materials. Results are ranked by relevance."
        )
    
    def _run(
        self,
        query: str,
        user_id: str,
        language: str = "auto",
        limit: int = 10
    ) -> str:
        """
        Execute the topic search.
        
        Args:
            query: Topic or concept to search for
            user_id: User ID for authorization
            language: Language for search ('de', 'en', or 'auto')
            limit: Maximum number of results
            
        Returns:
            JSON string with search results
        """
        try:
            results = search_page_analyses(
                user_id=user_id,
                query=query,
                language=language,
                limit=limit
            )
            
            if not results:
                return json.dumps({
                    "found": False,
                    "message": f"No pages found matching '{query}' in your courses.",
                    "results": []
                }, ensure_ascii=False)
            
            # Format results for agent consumption
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "course": {
                        "id": r.get("course_id"),
                        "title": r.get("course_title"),
                        "color": r.get("course_color")
                    },
                    "material": {
                        "id": r.get("material_id"),
                        "name": r.get("material_name")
                    },
                    "page_number": r.get("page_number"),
                    "summary": r.get("summary"),
                    "key_terms": r.get("key_terms"),
                    "relevance_score": r.get("rank")
                })
            
            # Pick the best introduction page: among highly relevant results, prefer lower page numbers
            # This ensures the LLM references the page that will actually be opened in the UI
            def pick_best_intro_page(search_results):
                if not search_results:
                    return None
                max_score = max(r.get("relevance_score", 0) or 0 for r in search_results)
                if max_score == 0:
                    return search_results[0]
                threshold = max_score * 0.7
                highly_relevant = [
                    r for r in search_results 
                    if (r.get("relevance_score", 0) or 0) >= threshold
                ]
                if highly_relevant:
                    return min(highly_relevant, key=lambda r: r.get("page_number", 999))
                return search_results[0]
            
            # Reorder results: put best intro page first, then others by relevance
            best_intro = pick_best_intro_page(formatted_results)
            if best_intro:
                # Move best intro page to front
                reordered_results = [best_intro] + [r for r in formatted_results if r != best_intro]
            else:
                reordered_results = formatted_results
            
            return json.dumps({
                "found": True,
                "message": f"Found {len(reordered_results)} page(s) matching '{query}'. The best starting point is page {best_intro.get('page_number') if best_intro else 'unknown'}.",
                "results": reordered_results,
                "recommended_page": best_intro.get("page_number") if best_intro else None
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to search topics: {str(e)}",
                "found": False,
                "results": []
            })
    
    async def _arun(
        self,
        query: str,
        user_id: str,
        language: str = "auto",
        limit: int = 10
    ) -> str:
        """
        Execute the topic search asynchronously.
        """
        return self._run(query, user_id, language, limit)
    
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
            args_schema=SearchTopicInput
        )
