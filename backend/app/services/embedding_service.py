"""
Embedding Generation Service

Generates vector embeddings for page summaries to enable semantic search.
Embeddings are generated in the background after PDF analysis completes.

Uses Google's text-embedding-004 model (768 dimensions) for consistency
with the rest of the project which uses Google Gemini.
"""

import asyncio
import logging
from typing import List, Optional, Tuple
from datetime import datetime, timezone

from google import genai
from app.core.config import settings
from app.adapters.supabase.client import get_supabase_client

logger = logging.getLogger(__name__)

# Embedding model configuration
# Google's text-embedding-004 produces 768-dimensional vectors
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSIONS = 768
BATCH_SIZE = 100  # Process in batches for efficiency

# Cached client instance
_genai_client = None


def _get_genai_client() -> genai.Client:
    """Get or create Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required for embedding generation")
        _genai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _genai_client


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text using Google's embedding model.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector (768 dimensions)
    """
    if not text or not text.strip():
        return []
    
    client = _get_genai_client()
    
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text.strip()
        )
        return list(result.embeddings[0].values)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise


async def generate_embedding_async(text: str) -> List[float]:
    """
    Generate embedding for a single text asynchronously.
    
    Note: Google's genai library doesn't have native async, so we run in thread pool.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        return []
    
    return await asyncio.to_thread(generate_embedding, text)


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a batch.
    
    Google's embed_content supports batch embedding via content list.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (in same order as input texts)
    """
    if not texts:
        return []
    
    # Clean texts and track which ones are valid
    cleaned_texts = []
    valid_indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            cleaned_texts.append(text.strip())
            valid_indices.append(i)
    
    if not cleaned_texts:
        return [[] for _ in texts]
    
    client = _get_genai_client()
    
    try:
        # Google's batch embedding
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=cleaned_texts
        )
        
        # Map embeddings back to original indices
        output = [[] for _ in texts]
        for resp_idx, embedding in enumerate(result.embeddings):
            original_idx = valid_indices[resp_idx]
            output[original_idx] = list(embedding.values)
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        raise


async def generate_embeddings_batch_async(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in a batch asynchronously.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (in same order as input texts)
    """
    if not texts:
        return []
    
    return await asyncio.to_thread(generate_embeddings_batch, texts)


def get_pages_without_embeddings(
    material_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100
) -> List[dict]:
    """
    Get pages that don't have embeddings yet.
    
    Args:
        material_id: Optional - filter by specific material
        user_id: Optional - filter by user
        limit: Maximum number of pages to return
        
    Returns:
        List of page analysis records without embeddings
    """
    client = get_supabase_client()
    
    try:
        query = (
            client.table("page_analyses")
            .select("id, summary, course_material_id, user_id")
            .or_("embedding_status.eq.pending,embedding_status.is.null")
            .limit(limit)
        )
        
        if material_id:
            query = query.eq("course_material_id", material_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.execute()
        return response.data or []
        
    except Exception as e:
        logger.error(f"Failed to get pages without embeddings: {e}")
        return []


def save_embedding(page_id: str, embedding: List[float]) -> bool:
    """
    Save an embedding for a page analysis.
    
    Args:
        page_id: Page analysis ID
        embedding: Embedding vector
        
    Returns:
        True if successful, False otherwise
    """
    if not embedding:
        return False
    
    client = get_supabase_client()
    
    try:
        # Convert to string format for pgvector
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        client.table("page_analyses").update({
            "summary_embedding": embedding_str,
            "embedding_status": "completed",
            "embedding_generated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", page_id).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to save embedding for page {page_id}: {e}")
        # Mark as failed so we can retry later
        try:
            client.table("page_analyses").update({
                "embedding_status": "failed"
            }).eq("id", page_id).execute()
        except Exception:
            pass
        return False


def save_embeddings_batch(page_embeddings: List[Tuple[str, List[float]]]) -> int:
    """
    Save multiple embeddings in batch.
    
    Args:
        page_embeddings: List of (page_id, embedding) tuples
        
    Returns:
        Number of successfully saved embeddings
    """
    success_count = 0
    
    for page_id, embedding in page_embeddings:
        if save_embedding(page_id, embedding):
            success_count += 1
    
    return success_count


def generate_embeddings_for_material(material_id: str) -> int:
    """
    Generate embeddings for all pages in a material.
    
    This is the main entry point for background embedding generation.
    Called after PDF analysis completes.
    
    Args:
        material_id: Course material ID
        
    Returns:
        Number of pages processed
    """
    logger.info(f"Starting embedding generation for material {material_id}")
    
    # Get all pages without embeddings for this material
    pages = get_pages_without_embeddings(material_id=material_id, limit=500)
    
    if not pages:
        logger.info(f"No pages need embeddings for material {material_id}")
        return 0
    
    logger.info(f"Generating embeddings for {len(pages)} pages")
    
    # Process in batches
    total_processed = 0
    
    for i in range(0, len(pages), BATCH_SIZE):
        batch = pages[i:i + BATCH_SIZE]
        
        # Mark as processing
        client = get_supabase_client()
        page_ids = [p["id"] for p in batch]
        try:
            for pid in page_ids:
                client.table("page_analyses").update({
                    "embedding_status": "processing"
                }).eq("id", pid).execute()
        except Exception as e:
            logger.warning(f"Failed to mark pages as processing: {e}")
        
        # Extract summaries
        summaries = [p.get("summary", "") or "" for p in batch]
        
        try:
            # Generate embeddings in batch
            embeddings = generate_embeddings_batch(summaries)
            
            # Save embeddings
            page_embeddings = list(zip(page_ids, embeddings))
            saved = save_embeddings_batch(page_embeddings)
            total_processed += saved
            
            logger.debug(f"Processed batch {i // BATCH_SIZE + 1}: {saved}/{len(batch)} saved")
            
        except Exception as e:
            logger.error(f"Failed to process batch: {e}")
            # Mark batch as failed
            for pid in page_ids:
                try:
                    client.table("page_analyses").update({
                        "embedding_status": "failed"
                    }).eq("id", pid).execute()
                except Exception:
                    pass
    
    logger.info(f"Completed embedding generation for material {material_id}: {total_processed} pages")
    return total_processed


async def generate_embeddings_for_material_async(material_id: str) -> int:
    """
    Generate embeddings for all pages in a material asynchronously.
    
    Args:
        material_id: Course material ID
        
    Returns:
        Number of pages processed
    """
    # Run the sync version in a thread pool to not block the event loop
    return await asyncio.to_thread(generate_embeddings_for_material, material_id)


def check_embedding_availability() -> bool:
    """
    Check if embedding generation is available (Google API key configured).
    
    Returns:
        True if embeddings can be generated, False otherwise
    """
    return bool(settings.GOOGLE_API_KEY)
