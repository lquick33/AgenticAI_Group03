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
            # Fetch more results than requested to enable better continuity calculation
            # This ensures we can find the actual chapter start even if it's not in the top N by raw relevance
            # We'll return only the requested limit after reordering
            internal_limit = max(limit * 3, 30)  # At least 30 or 3x the requested limit
            
            results = search_page_analyses(
                user_id=user_id,
                query=query,
                language=language,
                limit=internal_limit
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
                    "relevance_score": r.get("rank"),
                    "is_chapter_heading": r.get("is_chapter_heading", False),
                    "chapter_title": r.get("chapter_title")
                })
            
            # Pick the best introduction page using multiple strategies:
            # 1. If explicit chapter headings exist (is_chapter_heading=True), use those directly
            # 2. Fall back to heuristic-based detection for older materials without chapter data
            def pick_best_intro_page(search_results):
                if not search_results:
                    return None
                
                if len(search_results) == 1:
                    return search_results[0]
                
                # STRATEGY 0: Use explicit chapter headings (fast path for new materials)
                # The search already returns chapter headings first with high rank
                chapter_headings = [r for r in search_results if r.get("is_chapter_heading")]
                if chapter_headings:
                    # Prefer lowest page number among chapter headings (but skip page 1)
                    non_page1 = [r for r in chapter_headings if r.get("page_number", 1) > 1]
                    if non_page1:
                        return min(non_page1, key=lambda r: r.get("page_number", 999))
                    return min(chapter_headings, key=lambda r: r.get("page_number", 999))
                
                # FALLBACK: Heuristic-based detection for older materials
                query_lower = query.lower()
                query_base = query_lower[:-1] if len(query_lower) > 4 else query_lower
                
                def extract_stems(text: str, min_len: int = 4) -> set:
                    """Extract short stems from text for cross-language matching."""
                    words = text.lower().replace("-", " ").split()
                    stems = set()
                    for word in words:
                        clean = word.rstrip("s").rstrip("e").rstrip("n")
                        if len(clean) >= min_len:
                            stems.add(clean[:min(len(clean), 6)])
                    return stems
                
                query_stems = extract_stems(query_lower)
                
                def has_topic_as_primary(result):
                    """Check if topic appears in the first 2 key_terms (primary position)"""
                    key_terms = result.get("key_terms") or []
                    for kt in key_terms[:2]:
                        kt_lower = kt.lower()
                        if query_lower in kt_lower or kt_lower in query_lower or query_base in kt_lower:
                            return True
                        kt_stems = extract_stems(kt_lower)
                        if query_stems & kt_stems:
                            return True
                    return False
                
                def is_introduction(result):
                    """Check if summary indicates this is an introduction/chapter start"""
                    summary = (result.get("summary") or "").lower()
                    if summary.startswith("diese folie dient als einführung zu einem") and "beispiel" in summary[:80]:
                        return False
                    if summary.startswith("live") and "beispiel" in summary[:50]:
                        return False
                    if any(kw in summary for kw in ["einleitung", "einführung", "introduction"]):
                        return True
                    if "führt" in summary and "ein" in summary:
                        return True
                    return False
                
                # Heuristic Strategy 1: Topic is primary AND it's an introduction
                intro_candidates = [r for r in search_results if has_topic_as_primary(r) and is_introduction(r)]
                if intro_candidates:
                    non_page1 = [r for r in intro_candidates if r.get("page_number", 1) > 1]
                    if non_page1:
                        return min(non_page1, key=lambda r: r.get("page_number", 999))
                    return min(intro_candidates, key=lambda r: r.get("page_number", 999))
                
                # Heuristic Strategy 2: Topic is primary - use lowest page
                primary_candidates = [r for r in search_results if has_topic_as_primary(r)]
                if primary_candidates:
                    non_page1 = [r for r in primary_candidates if r.get("page_number", 1) > 1]
                    if non_page1:
                        return min(non_page1, key=lambda r: r.get("page_number", 999))
                
                # Heuristic Strategy 3: Weighted continuity for remaining cases
                def score_by_weighted_continuity(candidate):
                    material_id = candidate.get("material", {}).get("id")
                    page_num = candidate.get("page_number", 999)
                    weighted_continuity = 0.0
                    for r in search_results:
                        r_material = r.get("material", {}).get("id")
                        r_page = r.get("page_number", 0)
                        r_score = r.get("relevance_score", 0) or 0
                        if r_material == material_id and r_page > page_num and r_page <= page_num + 10:
                            weighted_continuity += r_score
                    return weighted_continuity
                
                pages_with_continuity = [(r, score_by_weighted_continuity(r)) for r in search_results]
                max_continuity = max(wc for _, wc in pages_with_continuity) if pages_with_continuity else 0
                
                if max_continuity > 0:
                    continuity_threshold = max_continuity * 0.4
                    good_candidates = [(r, wc) for r, wc in pages_with_continuity if wc >= continuity_threshold]
                    if good_candidates:
                        best = min(good_candidates, key=lambda x: x[0].get("page_number", 999))
                        return best[0]
                
                # Fallback: highest relevance score
                return max(search_results, key=lambda r: (r.get("relevance_score", 0) or 0, -r.get("page_number", 999)))
            
            # Reorder results: put best intro page first, then others by relevance
            best_intro = pick_best_intro_page(formatted_results)
            if best_intro:
                # Move best intro page to front
                reordered_results = [best_intro] + [r for r in formatted_results if r != best_intro]
            else:
                reordered_results = formatted_results
            
            # Limit to the requested number of results (we fetched more internally for continuity calculation)
            final_results = reordered_results[:limit]
            
            return json.dumps({
                "found": True,
                "message": f"Found {len(final_results)} page(s) matching '{query}'. The best starting point is page {best_intro.get('page_number') if best_intro else 'unknown'}.",
                "results": final_results,
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
