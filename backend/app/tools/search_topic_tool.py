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
from typing import Any, List, Optional, Tuple
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.services.storage import (
    search_page_analyses,
    search_page_analyses_multi,
    search_page_analyses_hybrid,
    check_embeddings_available,
    get_page_analyses_for_range,
)
from app.services.embedding_service import (
    generate_embedding,
    check_embedding_availability,
)
from app.services.observability import get_langfuse_client

logger = logging.getLogger(__name__)

# Langfuse prompt name for intro-page pick (load from Langfuse when available)
INTRO_PAGE_LLM_PROMPT_NAME = "search-topic/intro-page-pick"


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


# Fallback when Langfuse is disabled or prompt not found (variables: query, candidates_text)
INTRO_PAGE_LLM_PROMPT_FALLBACK = """The user wants to learn about: "{query}"

Below are candidate pages from their lecture materials. Each has: page number, material name, chapter/section title (if any), a short summary, and key terms.

{candidates_text}

Task: Which single page is the best **introduction / start** to learn this concept? Prefer:
- Section or chapter title slides that introduce the topic
- The first page of a block of related content (earlier page numbers when in doubt)
- Pages whose title or summary clearly introduces the concept

Return the page number (integer) of that page and a brief reason."""

# Max candidates and summary length for LLM intro-page pick (keep prompt fast/small)
INTRO_PAGE_LLM_MAX_CANDIDATES = 15
INTRO_PAGE_LLM_SUMMARY_MAX_CHARS = 180


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


class IntroPageChoice(BaseModel):
    """LLM output: best page as introduction/start for the concept."""
    best_page_number: int = Field(description="Page number of the best introduction/start page")
    reason: str = Field(description="Brief reason why this page is the best start")


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
    
    def _pick_best_intro_page_with_llm(
        self,
        query: str,
        candidates: List[dict],
        llm: Any,
    ) -> Optional[dict]:
        """
        Use LLM to pick the best introduction/start page from candidates.
        Returns the full result dict for that page, or None on failure.
        """
        if not candidates or not llm:
            return None
        try:
            structured_llm = llm.with_structured_output(IntroPageChoice)
            lines = []
            for i, c in enumerate(candidates[:INTRO_PAGE_LLM_MAX_CANDIDATES], 1):
                pn = c.get("page_number", 0)
                mat = (c.get("material") or {}).get("name", "")
                ch = c.get("chapter_title") or "-"
                summary = (c.get("summary") or "")[:INTRO_PAGE_LLM_SUMMARY_MAX_CHARS]
                if len(c.get("summary") or "") > INTRO_PAGE_LLM_SUMMARY_MAX_CHARS:
                    summary += "..."
                kt = (c.get("key_terms") or [])[:5]
                lines.append(
                    f"{i}. Page {pn} | Material: {mat} | Chapter/section: {ch}\n"
                    f"   Summary: {summary}\n   Key terms: {kt}"
                )
            candidates_text = "\n\n".join(lines)
            # Load prompt from Langfuse when available, else use fallback
            prompt = None
            langfuse_client = get_langfuse_client()
            if langfuse_client:
                try:
                    langfuse_prompt = langfuse_client.get_prompt(
                        INTRO_PAGE_LLM_PROMPT_NAME,
                        label="production",
                    )
                    prompt = langfuse_prompt.compile(
                        query=query,
                        candidates_text=candidates_text,
                    )
                    logger.debug("✅ Using Langfuse prompt for %s", INTRO_PAGE_LLM_PROMPT_NAME)
                except Exception as e:
                    logger.warning(
                        "Failed to load Langfuse prompt for intro-page-pick: %s, using fallback",
                        e,
                    )
            if not prompt:
                prompt = INTRO_PAGE_LLM_PROMPT_FALLBACK.format(
                    query=query,
                    candidates_text=candidates_text,
                )
            choice = structured_llm.invoke([HumanMessage(content=prompt)])
            if choice and getattr(choice, "best_page_number", None) is not None:
                pn = choice.best_page_number
                for c in candidates:
                    if c.get("page_number") == pn:
                        logger.info(f"LLM intro pick: page {pn}, reason: {getattr(choice, 'reason', '')[:80]}")
                        return c
                logger.warning(f"LLM returned page {pn} which is not in candidates")
        except Exception as e:
            logger.warning(f"LLM intro-page pick failed: {e}")
        return None
    
    def _pick_best_intro_page(
        self,
        search_results: List[dict],
        query: str,
        user_id: Optional[str] = None,
        return_score_breakdown: bool = False,
        llm: Optional[Any] = None,
    ):
        """
        Pick the best introduction page using multiple strategies.
        
        The goal is to find where a topic is INTRODUCED, not just mentioned.
        Continuity = avg correlation-to-query of the next 6 pages (from DB), not limited to search results.
        
        Args:
            search_results: List of formatted search results (candidates)
            query: Original search query for matching
            user_id: User ID for fetching following pages from DB; if None, continuity is 0 for all
            return_score_breakdown: If True, return (best, [(r, score, breakdown), ...])
            
        Returns:
            Best introduction page result, or None if no results.
            If return_score_breakdown is True, returns (best, scored_list).
        """
        if not search_results:
            return (None, []) if return_score_breakdown else None

        # Phase 2 (optional): LLM picks best intro from fast-retrieved candidates
        if llm:
            candidates = search_results[:INTRO_PAGE_LLM_MAX_CANDIDATES]
            best = self._pick_best_intro_page_with_llm(query, candidates, llm)
            if best is not None:
                if return_score_breakdown:
                    return best, []
                return best

        if len(search_results) == 1:
            if return_score_breakdown:
                return search_results[0], [(search_results[0], 0.0, {})]
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
            """Match score for title; prefer chapter_title when set. Apply focus factor: short,
            topic-focused titles score higher than long titles that add extra detail words."""
            title_text = result.get("chapter_title") or (result.get("key_terms") or [None])[0]
            if not title_text or not title_text.strip():
                return 0.0
            base = topic_match_score(title_text)
            if base <= 0:
                return 0.0
            words = [w for w in title_text.strip().split() if len(w) > 0]
            word_count = len(words)
            # Focus factor: boost short titles (more focused on topic), slight penalty for long (extra detail)
            if word_count <= 4:
                focus_mult = 1.0 + 0.12 * (4 - word_count) / 4  # 1 word -> 1.09, 2 -> 1.06, 3 -> 1.03, 4 -> 1.0
            else:
                focus_mult = 1.0 - 0.06 * min(word_count - 4, 5)  # 5 words -> 0.94, 9+ -> 0.70
            return min(1.0, base * focus_mult)
        
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
                
                # Among chapters with similar scores (within 0.25), prefer lowest page number (intro)
                # Wider threshold so e.g. "Klassendiagramm" p.6 (0.8) competes with "Klassendiagramme" p.28 (1.0)
                similar_chapters = [(ch, s) for ch, s in scored_chapters 
                                   if s >= best_score - 0.25 and ch.get("page_number", 1) > 1]
                if similar_chapters:
                    # Prefer earliest page: intro is usually first in document
                    best_ch = min(similar_chapters, key=lambda x: x[0].get("page_number", 999))[0]
                    return (best_ch, []) if return_score_breakdown else best_ch
                
                # Fallback: prefer non-page-1
                for ch, score in scored_chapters:
                    if ch.get("page_number", 1) > 1:
                        return (ch, []) if return_score_breakdown else ch
                best_ch = scored_chapters[0][0]
                return (best_ch, []) if return_score_breakdown else best_ch
        
        # AGGREGATE SCORING: Combine multiple signals
        # - semantic_score: from vector similarity (normalized 0-1)
        # - title_match: how well the title matches query (0-1)
        # - continuity_score: following pages relevance (introduction detection)
        # - material_relevance: materials with more matching pages get bonus
        #
        # WHY LATER PAGES (28, 37) CAN INCORRECTLY RANK HIGHER:
        # 1. Continuity score rewards pages that have many *following* matching pages.
        #    Later section intros often have more following pages in the result set.
        # 2. Chapter heading bonus (0.20) is equal for any matching chapter; it does
        #    not prefer the *earliest* chapter when multiple chapters match.
        # We do NOT use a flat "earliness" score (earlier page = better), because
        # chapters are sometimes introduced later in a lecture.
        
        # Pre-compute continuity: for each candidate, next 6 pages from DB, avg correlation to query
        continuity_scores = {}
        
        def page_correlation_to_query(page_dict: dict) -> float:
            """How much this page's content (key_terms) correlates to the query. 0-1."""
            key_terms = page_dict.get("key_terms") or []
            if not key_terms:
                return 0.0
            scores = [topic_match_score(kt) for kt in key_terms[:3]]
            return max(scores) if scores else 0.0
        
        if user_id:
            for r in search_results:
                mat_id = r.get("material", {}).get("id")
                page_num = r.get("page_number", 0)
                if not mat_id:
                    continue
                try:
                    following_pages = get_page_analyses_for_range(
                        mat_id, user_id, page_num + 1, page_num + 6
                    )
                except Exception as e:
                    logger.debug("Continuity fetch for material %s pages %s-%s: %s", mat_id[:8], page_num + 1, page_num + 6, e)
                    following_pages = []
                if following_pages:
                    correlations = [page_correlation_to_query(p) for p in following_pages]
                    avg = sum(correlations) / len(correlations)
                    # Scale down when fewer than 6 following pages (end of notes) so we don't
                    # give full weight to continuity computed from missing/cut-off pages
                    continuity_scores[(mat_id, page_num)] = avg * (len(following_pages) / 6.0)
        
        # First, find which materials have the most relevant pages
        material_page_counts = {}
        for r in search_results:
            mat_id = r.get("material", {}).get("id")
            if mat_id:
                material_page_counts[mat_id] = material_page_counts.get(mat_id, 0) + 1
        max_pages = max(material_page_counts.values()) if material_page_counts else 1
        
        def compute_aggregate_score(result) -> tuple[float, dict]:
            """Compute weighted aggregate score and breakdown for intro page selection."""
            # 1. Semantic similarity (from vector search, normalized)
            relevance = result.get("relevance_score", 0) or 0
            semantic_score = min(relevance * 100, 1.0)
            
            # 2. Title match quality
            title_score = get_title_match_score(result)
            
            # 3. Primary key_terms match
            primary_score = get_best_match_score(result)
            
            # 4. Continuity score
            page_num = result.get("page_number", 999)
            continuity_score = continuity_scores.get(
                (result.get("material", {}).get("id"), page_num), 
                0.0
            )
            if page_num == 1:
                continuity_score *= 0.5
            
            # 5. Material relevance
            mat_id = result.get("material", {}).get("id")
            mat_name = result.get("material", {}).get("name", "")
            mat_pages = material_page_counts.get(mat_id, 0)
            page_count_score = mat_pages / max_pages if max_pages > 0 else 0
            mat_name_score = topic_match_score(mat_name) if mat_name else 0
            material_score = max(page_count_score, mat_name_score * 0.8 + page_count_score * 0.2)
            
            # Value title-with-matching-material-name more highly (section title in the right lecture)
            synergy_bonus = 0.0
            if mat_name_score >= 0.4 and title_score >= 0.4:
                synergy_bonus = 0.22
            elif mat_name_score >= 0.3 and title_score >= 0.3:
                synergy_bonus = 0.12
            
            chapter_bonus = 0.0
            if result.get("is_chapter_heading") and title_score >= 0.3:
                chapter_bonus = 0.25
            
            # Weighted combination: find the START of the sub-part the student is searching for.
            # Title/chapter match is a strong signal (section start); continuity = following content.
            # Slightly more weight on title, continuity; less on semantic (retrieval already used it).
            aggregate = (
                title_score * 0.48 +
                primary_score * 0.16 +
                continuity_score * 0.24 +
                semantic_score * 0.08 +
                material_score * 0.18 +
                synergy_bonus +
                chapter_bonus
            )
            
            breakdown = {
                "page_number": page_num,
                "title_score": round(title_score, 3),
                "primary_score": round(primary_score, 3),
                "continuity_score": round(continuity_score, 3),
                "semantic_score": round(semantic_score, 3),
                "material_score": round(material_score, 3),
                "synergy_bonus": round(synergy_bonus, 3),
                "chapter_bonus": round(chapter_bonus, 3),
                "aggregate": round(aggregate, 3),
            }
            return aggregate, breakdown
        
        # Score all results (aggregate, breakdown)
        scored_results = []
        for r in search_results:
            agg, breakdown = compute_aggregate_score(r)
            scored_results.append((r, agg, breakdown))
        scored_results.sort(key=lambda x: -x[1])  # Highest score first
        
        # First-of-block bonus: among top-ranking results, if pages are adjacent (same material),
        # give a bonus to the first page of each block. Bonus scales with block length so the start
        # of a longer run (e.g. 30 with 30,31,32) beats the start of a short run (e.g. 42 alone, 52,53).
        FIRST_OF_BLOCK_TOP_N = 20
        FIRST_OF_BLOCK_BONUS_PER_PAGE = 0.1  # bonus = this * min(block_length, 5); longer runs win
        first_of_block_bonus: dict[Tuple[Optional[str], int], float] = {}
        top_for_blocks = scored_results[:FIRST_OF_BLOCK_TOP_N]
        by_material: dict[Optional[str], list[int]] = {}
        for r, _agg, _bd in top_for_blocks:
            mat_id = r.get("material", {}).get("id")
            pn = r.get("page_number")
            if mat_id is not None and pn is not None:
                by_material.setdefault(mat_id, []).append(pn)
        for mat_id, pages in by_material.items():
            if not pages:
                continue
            unique_pages = sorted(set(pages))
            i = 0
            while i < len(unique_pages):
                start = unique_pages[i]
                j = i
                while j + 1 < len(unique_pages) and unique_pages[j + 1] == unique_pages[j] + 1:
                    j += 1
                block_length = j - i + 1
                # Only give bonus when there is actually a block (2+ adjacent pages)
                if block_length >= 2:
                    bonus = FIRST_OF_BLOCK_BONUS_PER_PAGE * min(block_length, 5)
                    first_of_block_bonus[(mat_id, start)] = bonus
                i = j + 1
        # Earlier-block bonus: first block (earliest page) +0.10, second +0.05, third +0.03, etc.
        block_starts_sorted = sorted(first_of_block_bonus.keys(), key=lambda x: x[1])  # by page number
        EARLIER_BLOCK_BONUSES = (0.10, 0.05, 0.03, 0.02, 0.01)  # first, second, third, fourth, fifth+
        earlier_block_bonus: dict[Tuple[Optional[str], int], float] = {}
        for rank, (mat_id, start) in enumerate(block_starts_sorted):
            earlier_block_bonus[(mat_id, start)] = (
                EARLIER_BLOCK_BONUSES[rank] if rank < len(EARLIER_BLOCK_BONUSES) else EARLIER_BLOCK_BONUSES[-1]
            )
        # Apply bonus and re-sort by adjusted aggregate
        adjusted = []
        for r, agg, bd in scored_results:
            mat_id = r.get("material", {}).get("id")
            pn = r.get("page_number")
            length_bonus = first_of_block_bonus.get((mat_id, pn), 0.0)
            earlier_bonus = earlier_block_bonus.get((mat_id, pn), 0.0)
            bonus = length_bonus + earlier_bonus
            adjusted_agg = agg + bonus
            bd_with_bonus = {**bd, "first_of_block_bonus": round(bonus, 3)}
            if "aggregate" in bd_with_bonus:
                bd_with_bonus["aggregate"] = round(adjusted_agg, 3)
            adjusted.append((r, adjusted_agg, bd_with_bonus))
        adjusted.sort(key=lambda x: -x[1])
        scored_results = adjusted
        
        # Log score breakdown for top 5 to diagnose ranking (debug level)
        for r, score, breakdown in scored_results[:5]:
            logger.debug(
                "Intro page score p%d: %s",
                r.get("page_number"),
                breakdown,
            )
        
        # Return best result.
        # 1) If there are chapter headings in the top score band, prefer the EARLIEST one (section start).
        # 2) If there are multiple "first of block" pages in the top band, prefer the EARLIEST one so the
        #    real section start (e.g. p30 for Sequence Diagrams) beats a later block start (e.g. p52).
        # 3) Otherwise when scores are very close, tie-break in favor of earlier page.
        best_score = scored_results[0][1] if scored_results else 0
        CHAPTER_HEADING_EARLY_DELTA = 0.08  # Consider chapter headings within this band; pick earliest page
        chapter_headings_in_band = [
            (r, score, bd) for r, score, bd in scored_results
            if r.get("is_chapter_heading")
            and score >= best_score - CHAPTER_HEADING_EARLY_DELTA
            and r.get("page_number", 1) > 1
        ]
        if chapter_headings_in_band:
            best_r = min(chapter_headings_in_band, key=lambda x: x[0].get("page_number", 999))[0]
            if return_score_breakdown:
                return best_r, [(r, s, bd) for r, s, bd in scored_results]
            return best_r
        # Prefer earliest "first of block" when multiple are in the top band (p30 over p52 for sequence diagram)
        first_of_block_in_band = [
            (r, score, bd) for r, score, bd in scored_results
            if bd.get("first_of_block_bonus", 0) > 0
            and score >= best_score - CHAPTER_HEADING_EARLY_DELTA
            and r.get("page_number", 1) > 1
        ]
        if first_of_block_in_band:
            best_r = min(first_of_block_in_band, key=lambda x: x[0].get("page_number", 999))[0]
            if return_score_breakdown:
                return best_r, [(r, s, bd) for r, s, bd in scored_results]
            return best_r
        CLOSE_SCORE_DELTA = 0.03  # Tie-break when scores are close; prefer earlier page
        close_results = [
            (r, score, bd) for r, score, bd in scored_results
            if score >= best_score - CLOSE_SCORE_DELTA and r.get("page_number", 1) > 1
        ]
        if close_results:
            best_r = min(close_results, key=lambda x: x[0].get("page_number", 999))[0]
            if return_score_breakdown:
                return best_r, [(r, s, bd) for r, s, bd in scored_results]
            return best_r
        for r, score, _ in scored_results:
            if r.get("page_number", 1) > 1:
                if return_score_breakdown:
                    return r, [(res, s, bd) for res, s, bd in scored_results]
                return r
        best_r = scored_results[0][0] if scored_results else search_results[0]
        if return_score_breakdown:
            return best_r, [(r, s, bd) for r, s, bd in scored_results]
        return best_r
    
    def run_search_and_return_score_breakdown(
        self,
        query: str,
        user_id: str,
        language: str = "auto",
        limit: int = 30,
    ) -> Tuple[Optional[int], List[dict], List[Tuple[dict, float, dict]]]:
        """
        Run the same search as _run and return (best_page_number, formatted_results, scored_list).
        For testing/debugging intro-page scoring on real DB data.
        scored_list: [(result, aggregate_score, breakdown_dict), ...] sorted by score desc.
        """
        keywords = self._extract_keywords_sync(query)
        internal_limit = max(limit * 3, 30)
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
                        limit=internal_limit,
                    )
            except Exception as e:
                logger.warning(f"Hybrid search failed: {e}")
                results = None
        if results is None:
            if len(keywords) > 1:
                results = search_page_analyses_multi(
                    user_id=user_id,
                    queries=keywords,
                    language=language,
                    limit=internal_limit,
                )
            else:
                results = search_page_analyses(
                    user_id=user_id,
                    query=keywords[0] if keywords else query,
                    language=language,
                    limit=internal_limit,
                )
        if not results:
            return None, [], []
        formatted_results = []
        for r in results:
            formatted_results.append({
                "course": {"id": r.get("course_id"), "title": r.get("course_title"), "color": r.get("course_color")},
                "material": {"id": r.get("material_id"), "name": r.get("material_name")},
                "page_number": r.get("page_number"),
                "summary": r.get("summary"),
                "key_terms": r.get("key_terms"),
                "relevance_score": r.get("rank"),
                "is_chapter_heading": r.get("is_chapter_heading", False),
                "chapter_title": r.get("chapter_title"),
            })
        best_result, scored_list = self._pick_best_intro_page(
            formatted_results, query, user_id=user_id, return_score_breakdown=True, llm=self._llm
        )
        best_page = best_result.get("page_number") if best_result else None
        return best_page, formatted_results, scored_list
    
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
            
            # Pick the best introduction page and reorder results (LLM pick when self._llm set)
            best_intro = self._pick_best_intro_page(formatted_results, query, user_id=user_id, llm=self._llm)
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
            
            # Reuse the pick_best_intro_page logic from _run (LLM pick when self._llm set)
            best_intro = self._pick_best_intro_page(formatted_results, query, user_id=user_id, llm=self._llm)
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
