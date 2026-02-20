"""
Supabase Page Analysis adapter.

Implements PageAnalysisReader, PageAnalysisWriter, and PageAnalysisSearcher
using Supabase Postgres.

Extracted from app.services.storage (lines 145–198, 496–810, 987–1570).
"""

import logging
from time import time
from typing import Dict, List, Optional, Any, Tuple

from supabase import Client

from app.adapters.supabase.client import retry_on_resource_unavailable
from app.models.schemas import SlideAnalysis

logger = logging.getLogger(__name__)


# =============================================================================
# In-Memory Cache (co-located with the adapter that owns it)
# =============================================================================


class PageAnalysisCache:
    """
    In-memory TTL cache for page analyses.

    Page analyses are frequently accessed during chat sessions, so caching
    reduces database queries significantly.

    TTL: 5 minutes by default (300 seconds)
    """

    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds

    def get(
        self, material_id: str, page_number: int, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached page analysis. Returns None if missing or expired."""
        key = f"{material_id}:{page_number}:{user_id}"
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time() - timestamp < self._ttl:
                return data
            del self._cache[key]
        return None

    def set(
        self,
        material_id: str,
        page_number: int,
        user_id: str,
        analysis: Dict[str, Any],
    ) -> None:
        """Cache a page analysis."""
        key = f"{material_id}:{page_number}:{user_id}"
        self._cache[key] = (analysis, time())

    def invalidate(
        self, material_id: str, page_number: int, user_id: str
    ) -> None:
        """Remove a page analysis from cache."""
        key = f"{material_id}:{page_number}:{user_id}"
        if key in self._cache:
            del self._cache[key]

    def invalidate_material(self, material_id: str) -> None:
        """Remove all cached analyses for a material."""
        keys_to_delete = [
            k for k in self._cache.keys() if k.startswith(f"{material_id}:")
        ]
        for key in keys_to_delete:
            del self._cache[key]

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


# -- Internal retryable queries ------------------------------------------------


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_page_analysis(
    client: Client, course_material_id: str, page_number: int
) -> Optional[dict]:
    """Internal function to query page analysis (with retry logic)."""
    response = (
        client.table("page_analyses")
        .select(
            "id, summary, key_terms, exam_questions, diagram_description, "
            "raw_analysis, course_materials!inner(user_id)"
        )
        .eq("course_material_id", course_material_id)
        .eq("page_number", page_number)
        .execute()
    )
    return response.data[0] if response.data and len(response.data) > 0 else None


# =============================================================================
# Adapter
# =============================================================================


class SupabasePageAnalysisAdapter:
    """
    Concrete PageAnalysisReader + PageAnalysisWriter + PageAnalysisSearcher
    backed by Supabase Postgres.

    Handles page analysis CRUD, multi-tier search (chapter headings, FTS,
    ILIKE stem matching), multi-keyword search, hybrid RRF search, and
    embedding status checks.
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._cache = PageAnalysisCache()

    # -- PageAnalysisWriter Protocol -------------------------------------------

    def save(
        self,
        course_material_id: str,
        page_number: int,
        analysis: SlideAnalysis,
        user_id: str,
    ) -> dict:
        """
        Save page analysis to the page_analyses table.

        Returns:
            Created page_analysis record as dict
        """
        analysis_dict = analysis.model_dump()

        try:
            response = (
                self._client.table("page_analyses")
                .upsert(
                    {
                        "course_material_id": course_material_id,
                        "user_id": user_id,
                        "page_number": page_number,
                        "summary": analysis_dict["summary"],
                        "key_terms": analysis_dict["key_terms"],
                        "exam_questions": analysis_dict["exam_questions"],
                        "diagram_description": analysis_dict["diagram_description"],
                        "is_chapter_heading": analysis_dict.get(
                            "is_chapter_heading", False
                        ),
                        "chapter_title": analysis_dict.get("chapter_title"),
                        "raw_analysis": analysis_dict,
                    }
                )
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                raise Exception("Failed to save page_analysis")
        except Exception as e:
            raise Exception(f"Failed to save page analysis: {str(e)}")

    # -- PageAnalysisReader Protocol -------------------------------------------

    def get(
        self,
        course_material_id: str,
        page_number: int,
        user_id: str,
    ) -> dict:
        """
        Get page analysis data (with in-memory caching).

        Raises:
            ValueError: If page analysis not found or access denied
        """
        # Check cache first
        cached = self._cache.get(course_material_id, page_number, user_id)
        if cached is not None:
            logger.debug(
                f"Page analysis cache HIT for material "
                f"{course_material_id[:8]}... page {page_number}"
            )
            return cached

        try:
            analysis = _query_page_analysis(
                self._client, course_material_id, page_number
            )

            if not analysis:
                raise ValueError(
                    f"Page analysis not found for course_material_id="
                    f"{course_material_id}, page_number={page_number}"
                )

            # Validate ownership from joined data
            material_data = analysis.get("course_materials", {})
            material_user_id = (
                material_data.get("user_id") if material_data else None
            )

            if material_user_id != user_id:
                raise ValueError(
                    f"Access denied: user_id {user_id} does not match "
                    f"course material owner {material_user_id}"
                )

            result = {
                "summary": analysis.get("summary", ""),
                "key_terms": analysis.get("key_terms", []),
                "exam_questions": analysis.get("exam_questions", []),
                "diagram_description": analysis.get("diagram_description"),
                "raw_analysis": analysis.get("raw_analysis", {}),
            }

            # Cache the result
            self._cache.set(
                course_material_id, page_number, user_id, result
            )
            logger.debug(
                f"Page analysis cache MISS for material "
                f"{course_material_id[:8]}... page {page_number} (now cached)"
            )
            return result
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Failed to get page analysis: {str(e)}")

    def get_id(
        self,
        course_material_id: str,
        page_number: int,
        user_id: str,
    ) -> Optional[str]:
        """
        Get page analysis ID.

        Returns:
            Page analysis ID (UUID) or None if not found
        """
        try:
            response = (
                self._client.table("page_analyses")
                .select("id, course_materials!inner(user_id)")
                .eq("course_material_id", course_material_id)
                .eq("page_number", page_number)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return None

            analysis = response.data[0]

            # Validate ownership from joined data
            material_data = analysis.get("course_materials", {})
            material_user_id = (
                material_data.get("user_id") if material_data else None
            )

            if material_user_id != user_id:
                return None

            return analysis.get("id")
        except Exception as e:
            raise Exception(f"Failed to get page analysis ID: {str(e)}")

    def get_all_for_material(
        self,
        course_material_id: str,
        user_id: str,
    ) -> list:
        """
        Get all page analyses for a given course material.

        Used to aggregate per-page summaries for global topic generation.
        """
        try:
            response = (
                self._client.table("page_analyses")
                .select(
                    "id, page_number, summary, key_terms, "
                    "exam_questions, diagram_description"
                )
                .eq("course_material_id", course_material_id)
                .eq("user_id", user_id)
                .order("page_number", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as e:
            raise Exception(
                f"Failed to get page analyses for material: {str(e)}"
            )

    def get_for_range(
        self,
        course_material_id: str,
        user_id: str,
        start_page: int,
        end_page: int,
    ) -> list:
        """
        Get page analyses for a specific page range.

        Raises:
            ValueError: If course material not found or access denied
        """
        try:
            logger.info(
                f"🟡 Querying page_analyses: material={course_material_id}, "
                f"user={user_id}, pages={start_page}-{end_page}"
            )

            response = (
                self._client.table("page_analyses")
                .select(
                    "page_number, summary, key_terms, exam_questions, "
                    "diagram_description, raw_analysis, "
                    "course_materials!inner(user_id)"
                )
                .eq("course_material_id", course_material_id)
                .gte("page_number", start_page)
                .lte("page_number", end_page)
                .order("page_number", desc=False)
                .execute()
            )

            if not response.data:
                # Check if material exists vs no analyses in range
                material_check = (
                    self._client.table("course_materials")
                    .select("user_id")
                    .eq("id", course_material_id)
                    .execute()
                )

                if not material_check.data:
                    raise ValueError(
                        f"Course material not found: {course_material_id}"
                    )

                material_user_id = material_check.data[0].get("user_id")
                if material_user_id != user_id:
                    raise ValueError(
                        f"Access denied: user_id {user_id} does not match "
                        f"course material owner {material_user_id}"
                    )

                logger.warning(
                    f"⚠️ No page analyses found for range "
                    f"{start_page}-{end_page}"
                )
                return []

            # Validate ownership from first result
            first_result = response.data[0]
            material_data = first_result.get("course_materials", {})
            material_user_id = (
                material_data.get("user_id") if material_data else None
            )

            if material_user_id != user_id:
                raise ValueError(
                    f"Access denied: user_id {user_id} does not match "
                    f"course material owner {material_user_id}"
                )

            # Remove joined course_materials data from results
            result = []
            for item in response.data:
                clean_item = {
                    k: v for k, v in item.items() if k != "course_materials"
                }
                result.append(clean_item)

            logger.info(f"🟢 Query returned {len(result)} page analyses")
            if result:
                page_numbers = [r.get("page_number") for r in result]
                logger.debug(f"Page numbers found: {page_numbers}")

            return result

        except ValueError:
            raise
        except Exception as e:
            raise Exception(
                f"Failed to get page analyses for range: {str(e)}"
            )

    # -- PageAnalysisSearcher Protocol -----------------------------------------

    def search(
        self,
        user_id: str,
        query: str,
        language: str = "auto",
        limit: int = 10,
    ) -> List[dict]:
        """
        Multi-tier search across page analyses.

        Tier 1: Fast chapter heading search (indexed, ~10x faster)
        Tier 2: Full search with ILIKE + key_terms + stem-based scoring
        """
        if not query or not query.strip():
            return []

        sanitized_query = query.strip()
        query_lower = sanitized_query.lower()
        stem = (
            query_lower[: min(len(query_lower), 6)]
            if len(query_lower) >= 4
            else query_lower
        )

        try:
            # ── Tier 1: Fast chapter heading search ──
            tier1_results = None
            try:
                select_fields_chapter = (
                    "id, page_number, summary, key_terms, chapter_title, "
                    "course_material_id, "
                    "course_materials(id, file_name, course_id, "
                    "courses(id, title, color_code))"
                )

                chapter_response = (
                    self._client.table("page_analyses")
                    .select(select_fields_chapter)
                    .eq("user_id", user_id)
                    .eq("is_chapter_heading", True)
                    .ilike("chapter_title", f"%{stem}%")
                    .execute()
                )
                tier1_results = chapter_response.data
            except Exception as tier1_error:
                logger.debug(
                    f"Tier 1 search skipped (columns may not exist): "
                    f"{tier1_error}"
                )
                tier1_results = None

            if tier1_results:
                chapter_results = []
                for pa in tier1_results:
                    material = pa.get("course_materials") or {}
                    course = material.get("courses") or {}

                    chapter_results.append(
                        self._format_search_result(pa, material, course, rank=100)
                    )

                chapter_results.sort(key=lambda x: x["page_number"])
                return chapter_results[:limit]

            # ── Tier 2: Full search ──
            query_terms = query_lower.split()

            select_fields = (
                "id, page_number, summary, key_terms, is_chapter_heading, "
                "chapter_title, course_material_id, "
                "course_materials(id, file_name, course_id, "
                "courses(id, title, color_code))"
            )

            # Query 1: Summary ILIKE with stem
            response1 = (
                self._client.table("page_analyses")
                .select(select_fields)
                .eq("user_id", user_id)
                .ilike("summary", f"%{stem}%")
                .execute()
            )

            # Query 2: Key terms array contains
            term_capitalized = (
                sanitized_query.capitalize() if sanitized_query else ""
            )
            term_base = (
                sanitized_query[:-1]
                if len(sanitized_query) > 4
                else sanitized_query
            )
            term_base_cap = term_base.capitalize()

            key_terms_filter = f'key_terms.cs.{{"{term_capitalized}"}}'
            if term_base_cap != term_capitalized:
                key_terms_filter += f',key_terms.cs.{{"{term_base_cap}"}}'

            response2 = (
                self._client.table("page_analyses")
                .select(select_fields)
                .eq("user_id", user_id)
                .or_(key_terms_filter)
                .execute()
            )

            # Merge results (deduplicate)
            merged = {}
            for r in response1.data or []:
                merged[r["id"]] = r
            for r in response2.data or []:
                if r["id"] not in merged:
                    merged[r["id"]] = r

            if not merged:
                return []

            # Score results using stem-based relevance ranking
            query_stems = self._extract_stems(query_lower)

            results = []
            for pa in merged.values():
                summary = (pa.get("summary") or "").lower()
                key_terms = [kt.lower() for kt in (pa.get("key_terms") or [])]
                key_terms_text = " ".join(key_terms)
                key_terms_stems = self._extract_stems(key_terms_text)

                score = 0
                for term in query_terms:
                    if term in summary or any(
                        word.startswith(term[: min(len(term), 6)])
                        for word in summary.split()
                        if len(word) >= 4
                    ):
                        score += 2
                    if any(term in kt or kt in term for kt in key_terms):
                        score += 3
                    elif query_stems & key_terms_stems:
                        score += 3
                    if term in key_terms_text:
                        score += 1

                if score > 0:
                    material = pa.get("course_materials") or {}
                    course = material.get("courses") or {}
                    results.append(
                        self._format_search_result(
                            pa, material, course, rank=score
                        )
                    )

            results.sort(key=lambda x: x["rank"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to search page analyses: {str(e)}")
            raise Exception(f"Failed to search page analyses: {str(e)}")

    def search_multi(
        self,
        user_id: str,
        queries: List[str],
        language: str = "auto",
        limit: int = 10,
    ) -> List[dict]:
        """
        Multi-keyword OR search with deduplication and score aggregation.
        """
        if not queries:
            return []

        # Deduplicate queries
        clean_queries = []
        seen: set = set()
        for q in queries:
            q_clean = q.strip().lower()
            if q_clean and q_clean not in seen:
                clean_queries.append(q.strip())
                seen.add(q_clean)

        if not clean_queries:
            return []

        if len(clean_queries) == 1:
            return self.search(user_id, clean_queries[0], language, limit)

        try:
            all_results: dict = {}

            for query in clean_queries:
                try:
                    results = self.search(
                        user_id=user_id,
                        query=query,
                        language=language,
                        limit=limit * 2,
                    )

                    for r in results:
                        page_id = r.get("id")
                        if not page_id:
                            continue

                        if page_id in all_results:
                            existing = all_results[page_id]
                            existing["rank"] = (
                                existing.get("rank", 0) or 0
                            ) + (r.get("rank", 0) or 0)
                            existing["matched_queries"] = (
                                existing.get("matched_queries", 1) + 1
                            )
                        else:
                            r["matched_queries"] = 1
                            all_results[page_id] = r

                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                    continue

            if not all_results:
                return []

            results_list = list(all_results.values())
            results_list.sort(
                key=lambda x: (
                    x.get("matched_queries", 1),
                    x.get("rank", 0) or 0,
                ),
                reverse=True,
            )

            return results_list[:limit]

        except Exception as e:
            logger.error(
                f"Failed to search page analyses with multiple queries: "
                f"{str(e)}"
            )
            raise Exception(f"Failed to search page analyses: {str(e)}")

    def search_hybrid(
        self,
        user_id: str,
        query: str,
        query_embedding: List[float],
        language: str = "auto",
        limit: int = 10,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> List[dict]:
        """
        Hybrid search combining vector similarity and keyword FTS.

        Uses Reciprocal Rank Fusion (RRF) to combine results from both
        search methods.
        """
        if not query or not query.strip():
            return []

        try:
            fetch_limit = limit * 3

            # 1. Vector similarity search
            vector_results = []
            if query_embedding and len(query_embedding) > 0:
                try:
                    embedding_str = (
                        f"[{','.join(str(x) for x in query_embedding)}]"
                    )

                    response = self._client.rpc(
                        "search_pages_by_embedding",
                        {
                            "p_user_id": user_id,
                            "p_query_embedding": embedding_str,
                            "p_limit": fetch_limit,
                        },
                    ).execute()

                    if response.data:
                        vector_results = response.data
                        logger.debug(
                            f"Vector search returned "
                            f"{len(vector_results)} results"
                        )
                except Exception as e:
                    logger.debug(f"Vector search skipped: {e}")

            # 2. Keyword full-text search
            keyword_results = self.search(
                user_id=user_id,
                query=query,
                language=language,
                limit=fetch_limit,
            )
            logger.debug(
                f"Keyword search returned {len(keyword_results)} results"
            )

            # 3. Reciprocal Rank Fusion (RRF)
            K = 60
            fusion_scores: dict = {}

            # Add vector results
            for rank, result in enumerate(vector_results):
                page_id = result.get("id")
                if not page_id:
                    continue

                rrf_contribution = vector_weight * (1.0 / (K + rank + 1))

                if page_id in fusion_scores:
                    fusion_scores[page_id]["rrf_score"] += rrf_contribution
                    fusion_scores[page_id]["vector_rank"] = rank + 1
                else:
                    fusion_scores[page_id] = {
                        "rrf_score": rrf_contribution,
                        "vector_rank": rank + 1,
                        "keyword_rank": None,
                        "data": result,
                    }

            # Add keyword results
            for rank, result in enumerate(keyword_results):
                page_id = result.get("id")
                if not page_id:
                    continue

                rrf_contribution = keyword_weight * (1.0 / (K + rank + 1))

                if page_id in fusion_scores:
                    fusion_scores[page_id]["rrf_score"] += rrf_contribution
                    fusion_scores[page_id]["keyword_rank"] = rank + 1
                    if "material_id" in result:
                        fusion_scores[page_id]["data"] = result
                else:
                    fusion_scores[page_id] = {
                        "rrf_score": rrf_contribution,
                        "vector_rank": None,
                        "keyword_rank": rank + 1,
                        "data": result,
                    }

            if not fusion_scores:
                return []

            # 4. Sort by RRF score
            sorted_results = sorted(
                fusion_scores.values(),
                key=lambda x: x["rrf_score"],
                reverse=True,
            )

            final_results = []
            for entry in sorted_results[:limit]:
                result = entry["data"].copy()
                result["rank"] = entry["rrf_score"]
                result["vector_rank"] = entry["vector_rank"]
                result["keyword_rank"] = entry["keyword_rank"]
                final_results.append(result)

            return final_results

        except Exception as e:
            logger.error(f"Failed hybrid search: {str(e)}")
            return self.search(user_id, query, language, limit)

    def has_embeddings(self, user_id: str) -> bool:
        """
        Check if any embeddings are available for a user's materials.

        Used to decide between hybrid and keyword-only search.
        """
        try:
            response = (
                self._client.table("page_analyses")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("embedding_status", "completed")
                .limit(1)
                .execute()
            )
            return (response.count or 0) > 0
        except Exception:
            return False

    # -- Private helpers -------------------------------------------------------

    @staticmethod
    def _extract_stems(text: str, min_len: int = 4) -> set:
        """Extract short stems from text for cross-language matching."""
        words = text.lower().replace("-", " ").split()
        stems = set()
        for word in words:
            clean = word.rstrip("s").rstrip("e").rstrip("n")
            if len(clean) >= min_len:
                stems.add(clean[: min(len(clean), 6)])
        return stems

    @staticmethod
    def _format_search_result(
        pa: dict, material: dict, course: dict, rank: int
    ) -> dict:
        """Format a page analysis + joined data into a search result dict."""
        return {
            "id": pa.get("id"),
            "page_number": pa.get("page_number"),
            "summary": pa.get("summary"),
            "key_terms": pa.get("key_terms"),
            "chapter_title": pa.get("chapter_title"),
            "is_chapter_heading": pa.get("is_chapter_heading", False),
            "material_id": pa.get("course_material_id"),
            "material_name": material.get("file_name"),
            "course_id": material.get("course_id"),
            "course_title": course.get("title"),
            "course_color": course.get("color_code"),
            "rank": rank,
            "material": {
                "id": pa.get("course_material_id"),
                "name": material.get("file_name"),
            },
            "course": {
                "id": material.get("course_id"),
                "title": course.get("title"),
                "color": course.get("color_code"),
            },
        }
