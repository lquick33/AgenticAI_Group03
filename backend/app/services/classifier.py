"""
Material Classification Service

Provides reusable classification logic for categorizing course materials
into domain-specific types (language_learning, math, business_administration, general).
"""

import logging
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage

from app.services.storage import get_all_page_analyses_for_material
from app.services.analyzer import get_gemini_model
from app.services.observability import get_langfuse_client, create_callback_handler
from app.models.schemas import MaterialClassification

logger = logging.getLogger(__name__)


async def classify_material(
    material_id: str,
    user_id: str,
    course_id: str
) -> Dict[str, Any]:
    """
    Classify a material into a domain-specific category.
    
    Analyzes aggregated page content (summaries and key terms) to determine
    the material type using an LLM.
    
    Args:
        material_id: Course material ID
        user_id: User ID
        course_id: Course ID (for metadata)
        
    Returns:
        Dict with keys:
            - category: Classification category (language_learning, math, business_administration, general)
            - confidence: Confidence score (0.0-1.0)
            - reasoning: Brief explanation of classification
            
    Raises:
        Exception: If classification fails (caller should handle gracefully)
    """
    logger.info(f"Classifying material {material_id}")
    
    # Get all page analyses
    page_analyses = get_all_page_analyses_for_material(
        course_material_id=material_id,
        user_id=user_id
    )
    
    if not page_analyses:
        logger.warning(f"No page analyses available for material {material_id}, defaulting to general")
        return {
            "category": "general",
            "confidence": 0.5,
            "reasoning": "No page analyses available, defaulting to general"
        }
    
    # Aggregate content from all pages
    summaries = [p.get("summary", "") for p in page_analyses if p.get("summary")]
    key_terms = []
    for p in page_analyses:
        key_terms.extend(p.get("key_terms", []))
    
    if not summaries:
        logger.warning(f"No summaries found in page analyses for material {material_id}, defaulting to general")
        return {
            "category": "general",
            "confidence": 0.5,
            "reasoning": "No summaries found in page analyses, defaulting to general"
        }
    
    # Get classification prompt
    prompt = _get_classification_prompt(summaries, key_terms)
    
    # Use structured output
    llm = get_gemini_model()
    classification_llm = llm.with_structured_output(MaterialClassification)
    
    # Create Langfuse callback
    callback_handler = create_callback_handler()
    config = {}
    if callback_handler:
        config["callbacks"] = [callback_handler]
        config["metadata"] = {
            "langfuse_user_id": user_id,
            "langfuse_session_id": material_id,
            "material_id": material_id,
            "course_id": course_id,
            "operation": "classification"
        }
    
    try:
        message = HumanMessage(content=prompt)
        result = classification_llm.invoke([message], config=config if config else None)
        
        classification_result = {
            "category": result.category,
            "confidence": result.confidence,
            "reasoning": result.reasoning
        }
        
        logger.info(f"Successfully classified material {material_id} as: {classification_result['category']} (confidence: {classification_result['confidence']})")
        return classification_result
        
    except Exception as e:
        logger.error(f"Error in LLM classification for material {material_id}: {e}", exc_info=True)
        # Fallback to general on error
        return {
            "category": "general",
            "confidence": 0.3,
            "reasoning": f"Classification failed: {str(e)}"
        }


def _get_classification_prompt(summaries: List[str], key_terms: List[str]) -> str:
    """
    Get classification prompt from Langfuse.
    
    Falls back to hardcoded prompt if Langfuse unavailable.
    
    Args:
        summaries: List of page summaries
        key_terms: List of key terms from all pages
        
    Returns:
        Compiled prompt string
    """
    langfuse_client = get_langfuse_client()
    
    if not langfuse_client:
        return _get_fallback_classification_prompt(summaries, key_terms)
    
    try:
        langfuse_prompt = langfuse_client.get_prompt(
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
        return _get_fallback_classification_prompt(summaries, key_terms)


def _get_fallback_classification_prompt(summaries: List[str], key_terms: List[str]) -> str:
    """Fallback prompt if Langfuse unavailable."""
    summaries_text = "\n".join(summaries[:10])
    key_terms_text = ", ".join(key_terms[:50])
    
    return f"""Analyze the following lecture material and classify it into one of these categories:
- language_learning: Materials focused on vocabulary, grammar, translations, language practice, verb conjugations, pronunciation guides, language-specific terminology
- math: Materials with formulas, equations, proofs, mathematical concepts, derivatives, integrals, theorems, mathematical notation, problem sets
- business_administration: Materials covering business models, case studies, management concepts, strategy, marketing, financial terms, organizational behavior
- general: General educational materials without specific domain focus, mixed content, or content that doesn't clearly fit the above categories

**Material Content:**

Page Summaries:
{summaries_text}

Key Terms: {key_terms_text}

**Instructions:**
1. Analyze the page summaries and key terms to identify the primary domain
2. Look for domain-specific indicators:
   - Language learning: vocabulary lists, grammar rules, translations, verb forms, language exercises
   - Math: mathematical formulas, equations, proofs, calculus, algebra, geometry concepts
   - Business: case studies, business models, management theories, marketing strategies, financial concepts
3. Determine the most appropriate category
4. Provide a confidence score (0.0 to 1.0) based on how clearly the material fits the category
5. Provide brief reasoning (1-2 sentences) explaining your classification choice

**Output Format:**
You must respond with a valid JSON object matching this exact structure:
{{
  "category": "one of: language_learning, math, business_administration, or general",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation (1-2 sentences)"
}}"""
