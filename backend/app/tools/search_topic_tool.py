"""
Tool for searching topics across all user's courses and materials.

Used by the Quick Chat agent to find where a topic is discussed in lectures.
Supports three search modes:
1. Hybrid search (vector + keyword) when embeddings are available
2. Multi-keyword search with LLM keyword extraction
3. Simple keyword search as fallback
"""

import json
import logging
from typing import Any, List, Optional
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.services.storage import (
    search_page_analyses,
    search_page_analyses_multi,
    search_page_analyses_hybrid,
    check_embeddings_available,
)
from app.services.embedding_service import (
    generate_embedding,
    check_embedding_availability,
)

logger = logging.getLogger(__name__)


# Keyword extraction prompt - extracts searchable keywords from natural language questions
KEYWORD_EXTRACTION_PROMPT = """Extract 3-5 search keywords from this user question for searching lecture materials.

IMPORTANT:
- Include BOTH German AND English terms where applicable
- Include the main topic/concept being asked about
- Include synonyms and related technical terms
- Return as a JSON array of strings, nothing else

Examples:
- "How do I draw a class diagram?" → ["Klassendiagramm", "class diagram", "UML", "Klasse"]
- "What is inheritance in OOP?" → ["Vererbung", "inheritance", "OOP", "Objektorientierung"]
- "Explain the singleton pattern" → ["Singleton", "Design Pattern", "Entwurfsmuster"]

Question: {query}

Return ONLY a JSON array, no explanation:"""


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
    
    Uses LLM-based keyword extraction + full-text search to find pages 
    where a topic is discussed, returning context about the course, 
    material, and page location.
    
    The keyword extraction step converts natural language questions into
    searchable keywords in both German and English for better results.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the search topic tool.
        
        Args:
            llm: Optional LangChain LLM for keyword extraction. If not provided,
                 keyword extraction is skipped and the raw query is used.
        """
        self.name = "search_topic"
        self.description = (
            "Searches for a topic or concept across ALL of the user's courses and lecture materials. "
            "Returns a list of pages where the topic is discussed, including the course name, "
            "lecture/material name, page number, and a summary of the content. "
            "Use this tool when the user asks about a topic and you need to find where it's covered "
            "in their lecture materials. Results are ranked by relevance."
        )
        self._llm = llm
    
    def _extract_keywords_sync(self, query: str) -> List[str]:
        """
        Extract searchable keywords from a natural language query using LLM.
        
        Args:
            query: The user's natural language question
            
        Returns:
            List of extracted keywords (German and English)
        """
        if not self._llm:
            # No LLM available, return original query as single keyword
            return [query]
        
        try:
            prompt = KEYWORD_EXTRACTION_PROMPT.format(query=query)
            response = self._llm.invoke([HumanMessage(content=prompt)])
            
            # Parse JSON array from response
            content = response.content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            keywords = json.loads(content)
            
            if isinstance(keywords, list) and len(keywords) > 0:
                logger.debug(f"Extracted keywords for '{query}': {keywords}")
                # Always include original query as fallback
                if query not in keywords:
                    keywords.append(query)
                return keywords[:6]  # Limit to 6 keywords max
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse keyword extraction response: {e}")
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
        
        # Fallback to original query
        return [query]
    
    async def _extract_keywords_async(self, query: str) -> List[str]:
        """
        Extract searchable keywords from a natural language query using LLM (async).
        
        Args:
            query: The user's natural language question
            
        Returns:
            List of extracted keywords (German and English)
        """
        if not self._llm:
            return [query]
        
        try:
            prompt = KEYWORD_EXTRACTION_PROMPT.format(query=query)
            response = await self._llm.ainvoke([HumanMessage(content=prompt)])
            
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            keywords = json.loads(content)
            
            if isinstance(keywords, list) and len(keywords) > 0:
                logger.debug(f"Extracted keywords for '{query}': {keywords}")
                if query not in keywords:
                    keywords.append(query)
                return keywords[:6]
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse keyword extraction response: {e}")
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
        
        return [query]
    
    def _pick_best_intro_page(self, search_results: List[dict], query: str) -> Optional[dict]:
        """
        Pick the best introduction page using multiple strategies.
        
        The goal is to find where a topic is INTRODUCED, not just mentioned.
        A good introduction page typically:
        - Has the topic as its title/primary key term
        - Is followed by more pages about the same topic (continuity)
        - Contains introduction-like language
        
        Args:
            search_results: List of formatted search results
            query: Original search query for matching
            
        Returns:
            Best introduction page result, or None if no results
        """
        if not search_results:
            return None
        
        if len(search_results) == 1:
            return search_results[0]
        
        # STRATEGY 0: Use explicit chapter headings with title match (fast path for new materials)
        # Chapter headings are very reliable - they're explicitly marked as section starts
        chapter_headings = [r for r in search_results if r.get("is_chapter_heading")]
        # Will score chapter headings after defining topic_match_score below
        
        # Helper functions for matching
        query_lower = query.lower()
        query_words = [w for w in query_lower.replace("-", " ").split() if len(w) >= 3]
        
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
        # Get significant query words (skip common words)
        skip_words = {"was", "ist", "sind", "wie", "wo", "wer", "the", "what", "how", "is", "are"}
        significant_query_words = [w for w in query_words if w not in skip_words and len(w) >= 3]
        
        # Cross-language equivalents for common technical terms
        cross_lang = {
            "class": ["klasse", "klassen"], "klasse": ["class"], "klassen": ["class"],
            "diagram": ["diagramm", "diagramme"], "diagramm": ["diagram"], "diagramme": ["diagram", "diagrams"],
            "sequence": ["sequenz"], "sequenz": ["sequence"],
            "security": ["sicherheit"], "sicherheit": ["security"],
            "management": ["verwaltung"], "verwaltung": ["management"],
            "object": ["objekt"], "objekt": ["object"],
            "interface": ["schnittstelle"], "schnittstelle": ["interface"],
            "inheritance": ["vererbung"], "vererbung": ["inheritance"],
            "attribute": ["attribut"], "attribut": ["attribute"],
            "method": ["methode"], "methode": ["method"],
        }
        
        def topic_match_score(key_term: str) -> float:
            """
            Score how well a key_term matches the query topic.
            Higher scores = more complete match.
            """
            kt_lower = key_term.lower()
            kt_normalized = kt_lower.replace("-", " ").replace("_", " ")
            kt_words = set(kt_normalized.split())
            kt_stems = extract_stems(kt_lower)
            
            # Count how many significant query words are covered
            covered_words = 0
            for qw in significant_query_words:
                # Check exact word match
                if qw in kt_words:
                    covered_words += 1
                    continue
                # Check if query word is substring (e.g., "sicherheit" in "sicherheitsmanagement")
                if qw in kt_normalized:
                    covered_words += 0.9
                    continue
                # Check stem match
                qw_stem = list(extract_stems(qw))
                if qw_stem and qw_stem[0] in kt_stems:
                    covered_words += 0.7
                    continue
                # Check cross-language match
                equivalents = cross_lang.get(qw, [])
                for equiv in equivalents:
                    if equiv in kt_words or equiv in kt_normalized:
                        covered_words += 0.85
                        break
            
            if not significant_query_words:
                return 0.0
            
            # Score is proportion of query covered (0.0 to 1.0)
            return covered_words / len(significant_query_words)
        
        def get_title_match_score(result) -> float:
            """Get the match score for the first key_term (title)."""
            key_terms = result.get("key_terms") or []
            if key_terms:
                return topic_match_score(key_terms[0])
            return 0.0
        
        def get_best_match_score(result) -> float:
            """Get the best match score from first 2 key_terms."""
            key_terms = result.get("key_terms") or []
            scores = [topic_match_score(kt) for kt in key_terms[:2]]
            return max(scores) if scores else 0.0
        
        # STRATEGY 0 (continued): Score chapter headings that match the query
        if chapter_headings:
            # Score each chapter heading by title match
            scored_chapters = []
            for ch in chapter_headings:
                title_score = get_title_match_score(ch)
                if title_score >= 0.4:  # Minimum match threshold
                    scored_chapters.append((ch, title_score))
            
            if scored_chapters:
                # Sort by score desc, then page number asc
                scored_chapters.sort(key=lambda x: (-x[1], x[0].get("page_number", 999)))
                best_score = scored_chapters[0][1]
                
                # Among chapters with similar scores (within 0.15), prefer lowest page number
                similar_chapters = [(ch, s) for ch, s in scored_chapters 
                                   if s >= best_score - 0.15 and ch.get("page_number", 1) > 1]
                if similar_chapters:
                    return min(similar_chapters, key=lambda x: x[0].get("page_number", 999))[0]
                
                # Fallback: prefer non-page-1
                for ch, score in scored_chapters:
                    if ch.get("page_number", 1) > 1:
                        return ch
                return scored_chapters[0][0]
        
        # AGGREGATE SCORING: Combine multiple signals
        # - semantic_score: from vector similarity (normalized 0-1)
        # - title_match: how well the title matches query (0-1)
        # - continuity_score: following pages relevance (introduction detection)
        # - material_relevance: materials with more matching pages get bonus
        
        # Pre-compute continuity scores using pages already in search results
        # (Avoids expensive DB queries - uses what we already have)
        continuity_scores = {}
        
        # Build a lookup of pages by material
        pages_by_material = {}
        for r in search_results:
            mat_id = r.get("material", {}).get("id")
            if mat_id:
                if mat_id not in pages_by_material:
                    pages_by_material[mat_id] = []
                pages_by_material[mat_id].append(r)
        
        # For each candidate, check following pages in the search results
        # Use their actual relevance scores (semantic similarity) instead of binary match
        for r in search_results[:10]:
            mat_id = r.get("material", {}).get("id")
            page_num = r.get("page_number", 0)
            if not mat_id:
                continue
            
            # Find following pages from same material in search results
            mat_pages = pages_by_material.get(mat_id, [])
            following_relevance = []
            for other in mat_pages:
                other_page = other.get("page_number", 0)
                if other_page > page_num and other_page <= page_num + 10:
                    # Use the actual relevance score from search (semantic similarity)
                    other_score = other.get("relevance_score", 0) or 0
                    # Normalize to 0-1 range (RRF scores are small, multiply by 100)
                    normalized = min(other_score * 100, 1.0)
                    following_relevance.append(normalized)
            
            if following_relevance:
                # Combine count and quality: more following pages = likely bigger section intro
                # Use: average_relevance * log2(count + 1) to reward more following pages
                import math
                avg_relevance = sum(following_relevance) / len(following_relevance)
                count_factor = math.log2(len(following_relevance) + 1)  # log2(2)=1, log2(4)=2, log2(8)=3
                continuity_scores[(mat_id, page_num)] = avg_relevance * count_factor / 3.0  # Normalize
        
        # First, find which materials have the most relevant pages
        material_page_counts = {}
        for r in search_results:
            mat_id = r.get("material", {}).get("id")
            if mat_id:
                material_page_counts[mat_id] = material_page_counts.get(mat_id, 0) + 1
        max_pages = max(material_page_counts.values()) if material_page_counts else 1
        
        def compute_aggregate_score(result) -> float:
            """Compute weighted aggregate score for intro page selection."""
            # 1. Semantic similarity (from vector search, normalized)
            relevance = result.get("relevance_score", 0) or 0
            # Normalize to roughly 0-1 range (RRF scores are typically small)
            semantic_score = min(relevance * 100, 1.0)
            
            # 2. Title match quality
            title_score = get_title_match_score(result)
            
            # 3. Primary key_terms match (slightly lower weight than title)
            primary_score = get_best_match_score(result)
            
            # 4. Continuity score - calculated separately below
            page_num = result.get("page_number", 999)
            
            # Use pre-computed continuity score (default 0)
            continuity_score = continuity_scores.get(
                (result.get("material", {}).get("id"), page_num), 
                0.0
            )
            
            # Small penalty for page 1 (usually title/overview, not content intro)
            if page_num == 1:
                continuity_score *= 0.5
            
            # 5. Material relevance - check material name AND page count
            mat_id = result.get("material", {}).get("id")
            mat_name = result.get("material", {}).get("name", "")
            mat_pages = material_page_counts.get(mat_id, 0)
            
            # Score based on page count
            page_count_score = mat_pages / max_pages if max_pages > 0 else 0
            
            # Also check if material NAME matches the query
            mat_name_score = topic_match_score(mat_name) if mat_name else 0
            
            # Combine: material name match is strong signal
            material_score = max(page_count_score, mat_name_score * 0.8 + page_count_score * 0.2)
            
            # Synergy bonus: when BOTH material name AND page title match query,
            # this page is very likely the intro to that topic in that material
            synergy_bonus = 0.0
            if mat_name_score >= 0.4 and title_score >= 0.4:
                synergy_bonus = 0.15  # Strong signal for intro page
            
            # Chapter heading bonus - explicit section starts are very reliable
            chapter_bonus = 0.0
            if result.get("is_chapter_heading") and title_score >= 0.3:
                chapter_bonus = 0.20  # Very strong signal
            
            # Weighted combination
            # Material relevance is important - a material with many matching pages
            # is likely THE source for this topic
            # Continuity helps find where topic is introduced (start of a sequence)
            # Title match helps identify the intro page within that material
            aggregate = (
                title_score * 0.20 +        # Title match
                primary_score * 0.10 +      # Key terms match
                continuity_score * 0.15 +   # Has following related pages = intro
                semantic_score * 0.10 +     # Vector similarity
                material_score * 0.25 +     # Material with many matches = primary source
                synergy_bonus +             # Material + title both match
                chapter_bonus               # Explicit chapter heading
            )
            
            return aggregate
        
        # Score all results
        scored_results = [(r, compute_aggregate_score(r)) for r in search_results]
        scored_results.sort(key=lambda x: -x[1])  # Highest score first
        
        # Return best result, preferring non-page-1
        for r, score in scored_results:
            if r.get("page_number", 1) > 1:
                return r
        
        # Fallback to highest scoring result
        return scored_results[0][0] if scored_results else search_results[0]
    
    def _run(
        self,
        query: str,
        user_id: str,
        language: str = "auto",
        limit: int = 10
    ) -> str:
        """
        Execute the topic search.
        
        Search strategy (in order of preference):
        1. Hybrid search (vector + keyword) when embeddings are available
        2. Multi-keyword search with LLM-extracted keywords
        3. Simple keyword search as fallback
        
        Args:
            query: Topic or concept to search for
            user_id: User ID for authorization
            language: Language for search ('de', 'en', or 'auto')
            limit: Maximum number of results
            
        Returns:
            JSON string with search results
        """
        try:
            # Step 1: Extract searchable keywords from the natural language query
            # This converts "How do I draw a class diagram?" into 
            # ["Klassendiagramm", "class diagram", "UML", "Klasse"]
            keywords = self._extract_keywords_sync(query)
            logger.info(f"Search keywords for '{query}': {keywords}")
            
            # Fetch more results than requested to enable better continuity calculation
            # This ensures we can find the actual chapter start even if it's not in the top N by raw relevance
            # We'll return only the requested limit after reordering
            internal_limit = max(limit * 3, 30)  # At least 30 or 3x the requested limit
            
            # Step 2: Try hybrid search if embeddings are available
            results = None
            used_hybrid = False
            
            if check_embedding_availability() and check_embeddings_available(user_id):
                try:
                    # Generate query embedding for vector search
                    # Use the first keyword (usually the main topic) for embedding
                    primary_query = keywords[0] if keywords else query
                    query_embedding = generate_embedding(primary_query)
                    
                    if query_embedding:
                        results = search_page_analyses_hybrid(
                            user_id=user_id,
                            query=primary_query,
                            query_embedding=query_embedding,
                            language=language,
                            limit=internal_limit
                        )
                        used_hybrid = True
                        logger.info(f"Used hybrid search for '{query}', found {len(results)} results")
                        
                except Exception as e:
                    logger.warning(f"Hybrid search failed, falling back to keyword search: {e}")
                    results = None
            
            # Step 3: Fallback to keyword search if hybrid didn't work or isn't available
            if results is None:
                if len(keywords) > 1:
                    results = search_page_analyses_multi(
                        user_id=user_id,
                        queries=keywords,
                        language=language,
                        limit=internal_limit
                    )
                    logger.info(f"Used multi-keyword search for '{query}', found {len(results)} results")
                else:
                    # Single keyword, use original function
                    results = search_page_analyses(
                        user_id=user_id,
                        query=keywords[0] if keywords else query,
                        language=language,
                        limit=internal_limit
                    )
                    logger.info(f"Used keyword search for '{query}', found {len(results)} results")
            
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
            
            # Pick the best introduction page and reorder results
            best_intro = self._pick_best_intro_page(formatted_results, query)
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
        
        Search strategy (in order of preference):
        1. Hybrid search (vector + keyword) when embeddings are available
        2. Multi-keyword search with LLM-extracted keywords
        3. Simple keyword search as fallback
        """
        try:
            # Extract keywords asynchronously
            keywords = await self._extract_keywords_async(query)
            logger.info(f"Search keywords for '{query}': {keywords}")
            
            internal_limit = max(limit * 3, 30)
            
            # Try hybrid search if embeddings are available
            results = None
            
            if check_embedding_availability() and check_embeddings_available(user_id):
                try:
                    primary_query = keywords[0] if keywords else query
                    query_embedding = generate_embedding(primary_query)
                    
                    if query_embedding:
                        results = search_page_analyses_hybrid(
                            user_id=user_id,
                            query=primary_query,
                            query_embedding=query_embedding,
                            language=language,
                            limit=internal_limit
                        )
                        logger.info(f"Used hybrid search for '{query}', found {len(results)} results")
                        
                except Exception as e:
                    logger.warning(f"Hybrid search failed, falling back to keyword search: {e}")
                    results = None
            
            # Fallback to keyword search
            if results is None:
                if len(keywords) > 1:
                    results = search_page_analyses_multi(
                        user_id=user_id,
                        queries=keywords,
                        language=language,
                        limit=internal_limit
                    )
                else:
                    results = search_page_analyses(
                        user_id=user_id,
                        query=keywords[0] if keywords else query,
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
            
            # Reuse the pick_best_intro_page logic from _run
            best_intro = self._pick_best_intro_page(formatted_results, query)
            if best_intro:
                reordered_results = [best_intro] + [r for r in formatted_results if r != best_intro]
            else:
                reordered_results = formatted_results
            
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
