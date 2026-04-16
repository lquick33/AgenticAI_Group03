"""
Flashcard Prompt Service

Handles prompt generation, caching, and Langfuse integration for the
FlashcardGeneratorAgent. Extracted to centralize prompt management.
"""

import logging
import threading
import time
from typing import List, Dict, Any, Optional, Tuple

from app.services.observability import get_langfuse_client

logger = logging.getLogger(__name__)


class PromptCache:
    """
    In-memory cache for Langfuse prompts with TTL.
    
    Eliminates network latency for repeated prompt fetches during
    flashcard generation (50-100ms saved per page after first fetch).
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize prompt cache.
        
        Args:
            ttl_seconds: Time-to-live for cached prompts (default 5 minutes)
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
    
    def get(self, prompt_name: str, langfuse_client, label: str = "production") -> Any:
        """
        Get prompt from cache or fetch from Langfuse.
        
        Args:
            prompt_name: Name of the prompt to fetch
            langfuse_client: Langfuse client instance
            label: Prompt label (default "production")
            
        Returns:
            Langfuse prompt object
        """
        cache_key = f"{prompt_name}:{label}"
        now = time.time()
        
        with self._lock:
            if cache_key in self._cache:
                cached_prompt, timestamp = self._cache[cache_key]
                if now - timestamp < self._ttl:
                    logger.debug(f"Prompt cache HIT: {prompt_name}")
                    return cached_prompt
        
        # Fetch from Langfuse
        logger.debug(f"Prompt cache MISS: {prompt_name}")
        prompt = langfuse_client.get_prompt(prompt_name, label=label)
        
        with self._lock:
            self._cache[cache_key] = (prompt, now)
        
        return prompt
    
    def clear(self) -> None:
        """Clear all cached prompts."""
        with self._lock:
            self._cache.clear()


class FlashcardPromptService:
    """Service for managing Langfuse prompts for flashcard generation."""
    
    def __init__(self):
        self.langfuse_client = get_langfuse_client()
        self.prompt_cache = PromptCache(ttl_seconds=300)
        
    def prepare_snippet_info(self, snippet_image_urls: Optional[List[str]]) -> str:
        """
        Prepare snippet information string for prompt.
        
        Args:
            snippet_image_urls: Optional list of snippet image URLs
            
        Returns:
            Formatted snippet info string
        """
        if not snippet_image_urls:
            return ""
            
        return f"\n\n**Visual Context:**\n- Available Snippet Elements: {len(snippet_image_urls)}"

    def get_classification_prompt(self, summaries: List[str], key_terms: List[str]) -> str:
        """
        Get classification prompt from Langfuse.
        
        Falls back to hardcoded prompt if Langfuse unavailable.
        
        Args:
            summaries: List of page summaries
            key_terms: List of key terms from all pages
            
        Returns:
            Compiled prompt string
        """
        if not self.langfuse_client:
            return self._get_fallback_classification_prompt(summaries, key_terms)
        
        try:
            langfuse_prompt = self.langfuse_client.get_prompt(
                "material-classifier/classification",
                label="production"
            )
            
            # Aggregate summaries (limit to avoid token explosion)
            summaries_text = "\n".join(summaries[:10])  # First 10 pages
            key_terms_text = ", ".join(key_terms[:50])  # First 50 terms
            
            compiled_prompt = langfuse_prompt.compile(
                page_summaries=summaries_text,
                key_terms=key_terms_text
            )
            return compiled_prompt
        except Exception as e:
            logger.warning(f"Failed to load Langfuse prompt: {e}, using fallback")
            return self._get_fallback_classification_prompt(summaries, key_terms)

    def _get_fallback_classification_prompt(self, summaries: List[str], key_terms: List[str]) -> str:
        """Fallback prompt if Langfuse unavailable."""
        summaries_text = "\n".join(summaries[:10])
        key_terms_text = ", ".join(key_terms[:50])
        
        return f"""Analyze the following lecture material and classify it into one of these categories:
- language_learning: Materials focused on vocabulary, grammar, translations, language practice
- math: Materials with formulas, equations, proofs, mathematical concepts
- business_administration: Materials covering business models, case studies, management concepts
- general: General educational materials without specific domain focus

Page Summaries:
{summaries_text}

Key Terms: {key_terms_text}

Based on the content, classify this material and provide:
1. The most appropriate category
2. A confidence score (0.0 to 1.0)
3. Brief reasoning for your choice

Respond with a JSON object matching this structure:
{{
  "category": "one of the categories above",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

    def get_skip_decision_prompt(self, summary: str, key_terms: List[str]) -> str:
        """
        Get skip decision prompt from Langfuse (cached).
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            
        Returns:
            Compiled prompt string
            
        Raises:
            RuntimeError: If Langfuse client is not available or prompt cannot be loaded
        """
        if not self.langfuse_client:
            raise RuntimeError("Langfuse client is not available. Cannot load skip-decision prompt.")
        
        try:
            langfuse_prompt = self.prompt_cache.get(
                "flashcard-agent/skip-decision",
                self.langfuse_client,
                label="production"
            )
            key_terms_str = ', '.join(key_terms[:10]) if key_terms else 'Keine'
            compiled_prompt = langfuse_prompt.compile(
                summary=summary,
                key_terms=key_terms_str
            )
            logger.debug("Using Langfuse prompt for skip-decision (cached)")
            return compiled_prompt
        except Exception as e:
            logger.error(f"Failed to load Langfuse prompt for skip-decision: {e}")
            raise RuntimeError(f"Cannot load skip-decision prompt from Langfuse: {e}") from e

    def _get_base_card_generation_prompt(self, compile_vars: Optional[Dict[str, Any]] = None) -> str:
        """Get base flashcard generation prompt from Langfuse (cached)."""
        if not self.langfuse_client:
            base_prompt = self._get_fallback_base_prompt()
            if compile_vars:
                base_prompt = base_prompt.replace("{{summary}}", compile_vars.get("summary", ""))
                base_prompt = base_prompt.replace("{{key_terms}}", compile_vars.get("key_terms", ""))
                base_prompt = base_prompt.replace("{{exam_questions}}", compile_vars.get("exam_questions", ""))
                base_prompt = base_prompt.replace("{{diagram_description}}", compile_vars.get("diagram_description", ""))
                base_prompt = base_prompt.replace("{{conversation_context}}", compile_vars.get("conversation_context", ""))
                base_prompt = base_prompt.replace("{{course_id}}", compile_vars.get("course_id", ""))
                base_prompt = base_prompt.replace("{{material_id}}", compile_vars.get("material_id", ""))
                base_prompt = base_prompt.replace("{{page_number}}", str(compile_vars.get("page_number", "")))
                base_prompt = base_prompt.replace("{{snippet_image_url}}", compile_vars.get("snippet_image_url", ""))
            return base_prompt
        
        try:
            langfuse_prompt = self.prompt_cache.get(
                "flashcard-agent/card-generation-base",
                self.langfuse_client,
                label="production"
            )
            if compile_vars:
                return langfuse_prompt.compile(**compile_vars)
            else:
                return langfuse_prompt.compile()
        except Exception as e:
            logger.warning(f"Failed to load base prompt from Langfuse: {e}, using fallback")
            base_prompt = self._get_fallback_base_prompt()
            if compile_vars:
                base_prompt = base_prompt.replace("{{summary}}", compile_vars.get("summary", ""))
                base_prompt = base_prompt.replace("{{key_terms}}", compile_vars.get("key_terms", ""))
                base_prompt = base_prompt.replace("{{exam_questions}}", compile_vars.get("exam_questions", ""))
                base_prompt = base_prompt.replace("{{diagram_description}}", compile_vars.get("diagram_description", ""))
                base_prompt = base_prompt.replace("{{conversation_context}}", compile_vars.get("conversation_context", ""))
                base_prompt = base_prompt.replace("{{course_id}}", compile_vars.get("course_id", ""))
                base_prompt = base_prompt.replace("{{material_id}}", compile_vars.get("material_id", ""))
                base_prompt = base_prompt.replace("{{page_number}}", str(compile_vars.get("page_number", "")))
                base_prompt = base_prompt.replace("{{snippet_image_url}}", compile_vars.get("snippet_image_url", ""))
            return base_prompt

    def get_card_generation_prompt(
        self,
        summary: str,
        key_terms: List[str],
        exam_questions: List[str],
        diagram_description: str,
        conversation_context: str,
        course_id: str,
        material_id: str,
        page_number: int,
        classification: Optional[str] = None,
        snippet_image_urls: Optional[List[str]] = None
    ) -> str:
        """
        Get card generation prompt from Langfuse based on classification.
        
        Args:
            summary: Page summary
            key_terms: List of key terms
            exam_questions: List of exam questions
            diagram_description: Diagram description
            conversation_context: Conversation context
            course_id: Course ID
            material_id: Material ID
            page_number: Page number
            classification: Material classification category
            snippet_image_urls: Optional list of snippet image URLs
            
        Returns:
            Compiled prompt string
        """
        classification = classification or "general"
        
        key_terms_str = ', '.join(key_terms) if key_terms else 'Keine'
        exam_questions_str = ', '.join(exam_questions) if exam_questions else 'Keine'
        diagram_desc_str = diagram_description if diagram_description else 'Kein Diagramm'
        conv_context_str = conversation_context if conversation_context else 'Keine relevanten Konversationen'
        
        snippet_info = self.prepare_snippet_info(snippet_image_urls)
        
        if not self.langfuse_client:
            return self._get_fallback_card_generation_prompt(
                classification, summary, key_terms_str, exam_questions_str,
                diagram_desc_str, conv_context_str, course_id, material_id,
                page_number, snippet_info
            )
        
        try:
            prompt_name = f"flashcard-agent/card-generation-{classification}"
            langfuse_prompt = self.prompt_cache.get(
                prompt_name,
                self.langfuse_client,
                label="production"
            )
            
            prompt_template = None
            if hasattr(langfuse_prompt, 'prompt'):
                prompt_template = str(langfuse_prompt.prompt)
            elif hasattr(langfuse_prompt, 'messages') and langfuse_prompt.messages:
                first_msg = langfuse_prompt.messages[0] if isinstance(langfuse_prompt.messages, list) else None
                if first_msg and hasattr(first_msg, 'content'):
                    prompt_template = str(first_msg.content)
                elif isinstance(first_msg, dict) and 'content' in first_msg:
                    prompt_template = str(first_msg['content'])
            else:
                try:
                    prompt_template = langfuse_prompt.compile()
                except:
                    pass
            
            uses_base_prompt = prompt_template and "{{base_prompt_content}}" in prompt_template
            SNIPPET_PLACEHOLDER = "___SNIPPET_IMAGE_URL_PLACEHOLDER___"
            
            compile_vars = {
                "summary": summary,
                "key_terms": key_terms_str,
                "exam_questions": exam_questions_str,
                "diagram_description": diagram_desc_str,
                "conversation_context": conv_context_str,
                "course_id": course_id,
                "material_id": material_id,
                "page_number": str(page_number),
                "snippet_image_url": SNIPPET_PLACEHOLDER
            }
            
            if uses_base_prompt:
                base_prompt_content = self._get_base_card_generation_prompt(compile_vars=compile_vars)
                compile_vars["base_prompt_content"] = base_prompt_content
                logger.info(f"Using base prompt + {classification}-specific prompt")
            else:
                logger.info(f"Using standalone {classification}-specific prompt (no base)")
            
            compiled = langfuse_prompt.compile(**compile_vars)
            
            # Handle snippet snippet replacing logic
            if snippet_image_urls:
                placeholder_count = compiled.count(SNIPPET_PLACEHOLDER)
                if placeholder_count > 0:
                    parts = compiled.split(SNIPPET_PLACEHOLDER, placeholder_count)
                    if len(parts) >= 2:
                        result_parts = [parts[0]]
                        result_parts.append(snippet_info)
                        primary_url = snippet_image_urls[0]
                        for i in range(1, len(parts) - 1):
                            result_parts.append(primary_url)
                            result_parts.append(parts[i])
                        if len(parts) > 1:
                            result_parts.append(primary_url)
                            result_parts.append(parts[-1])
                        compiled = "".join(result_parts)
                    else:
                        compiled = compiled.replace(SNIPPET_PLACEHOLDER, snippet_info)
            else:
                compiled = compiled.replace(SNIPPET_PLACEHOLDER, "")
            
            return compiled
            
        except Exception as e:
            logger.warning(f"Failed to load {classification} prompt: {e}, trying general")
            if classification != "general":
                return self.get_card_generation_prompt(
                    summary, key_terms, exam_questions, diagram_description,
                    conversation_context, course_id, material_id, page_number,
                    "general", snippet_image_urls
                )
            
            # Legacy fallback
            try:
                SNIPPET_PLACEHOLDER = "___SNIPPET_IMAGE_URL_PLACEHOLDER___"
                old_prompt_name = "flashcard-agent/card-generation"
                old_langfuse_prompt = self.prompt_cache.get(
                    old_prompt_name,
                    self.langfuse_client,
                    label="production"
                )
                
                compile_vars = {
                    "summary": summary,
                    "key_terms": key_terms_str,
                    "exam_questions": exam_questions_str,
                    "diagram_description": diagram_desc_str,
                    "conversation_context": conv_context_str,
                    "course_id": course_id,
                    "material_id": material_id,
                    "page_number": str(page_number),
                    "snippet_image_url": SNIPPET_PLACEHOLDER
                }
                
                compiled = old_langfuse_prompt.compile(**compile_vars)
                
                if snippet_image_urls:
                    placeholder_count = compiled.count(SNIPPET_PLACEHOLDER)
                    if placeholder_count > 0:
                        parts = compiled.split(SNIPPET_PLACEHOLDER, placeholder_count)
                        if len(parts) >= 2:
                            result_parts = [parts[0]]
                            result_parts.append(snippet_info)
                            primary_url = snippet_image_urls[0]
                            for i in range(1, len(parts) - 1):
                                result_parts.append(primary_url)
                                result_parts.append(parts[i])
                            if len(parts) > 1:
                                result_parts.append(primary_url)
                                result_parts.append(parts[-1])
                            compiled = "".join(result_parts)
                        else:
                            compiled = compiled.replace(SNIPPET_PLACEHOLDER, snippet_info)
                else:
                    compiled = compiled.replace(SNIPPET_PLACEHOLDER, "")
                
                return compiled
            except Exception as old_prompt_error:
                logger.warning(f"Old prompt also not found: {old_prompt_error}, using hardcoded fallback")
            
            return self._get_fallback_card_generation_prompt(
                "general", summary, key_terms_str, exam_questions_str,
                diagram_desc_str, conv_context_str, course_id, material_id,
                page_number, snippet_info
            )

    def _get_fallback_base_prompt(self) -> str:
        """Fallback base prompt if Langfuse unavailable."""
        return """You are a flashcard generator that creates educational flashcards from lecture materials.

**General Instructions:**
- Create 1-2 flashcards per page based on content complexity
- Front side should be a clear question or prompt
- Back side should contain the answer with context
- Use appropriate tags for categorization
- Consider conversation context when available
- Include visual snippets when relevant

**Output Format:**
You must respond with a valid JSON object matching this structure:
{
  "cards": [
    {
      "front": "question or prompt",
      "back": "answer with context",
      "tags": ["tag1", "tag2"]
    }
  ]
}"""

    def _get_fallback_card_generation_prompt(
        self,
        classification: str,
        summary: str,
        key_terms: str,
        exam_questions: str,
        diagram_description: str,
        conversation_context: str,
        course_id: str,
        material_id: str,
        page_number: str,
        snippet_info: str
    ) -> str:
        """Fallback classification-specific prompt when Langfuse unavailable."""
        base_prompt = self._get_fallback_base_prompt()
        
        classification_additions = {
            "language_learning": "\n\n**Language Learning Focus:**\n- Focus on vocabulary, grammar, translations\n- Create cards for verb conjugations and word meanings\n- Include pronunciation hints when relevant\n- Use language-specific tags (e.g., \"vocabulary\", \"grammar\", \"verb\")",
            "math": "\n\n**Math Focus:**\n- Focus on formulas, equations, proofs\n- Create cards for mathematical concepts and problem-solving steps\n- Include step-by-step solutions when relevant\n- Use math-specific tags (e.g., \"formula\", \"theorem\", \"proof\")",
            "business_administration": "\n\n**Business Administration Focus:**\n- Focus on business models, case studies, management concepts\n- Create cards for strategic thinking and business terminology\n- Include real-world examples when relevant\n- Use business-specific tags (e.g., \"strategy\", \"case_study\", \"management\")",
            "general": ""
        }
        
        addition = classification_additions.get(classification, "")
        final_prompt = base_prompt + addition
        
        final_prompt += f"""

**Page Information:**
- Summary: {summary}
- Key Terms: {key_terms}
- Exam Questions: {exam_questions}
- Diagram Description: {diagram_description}
- Conversation Context: {conversation_context}
- Course ID: {course_id}
- Material ID: {material_id}
- Page Number: {page_number}
{snippet_info}"""
        
        return final_prompt
