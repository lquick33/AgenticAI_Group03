-- ============================================================================
-- Add Vector Embeddings for Semantic Search
-- 
-- This migration adds pgvector support for semantic search in QuickChat.
-- Embeddings are generated in the background after PDF analysis completes.
-- ============================================================================

-- 1. Enable pgvector extension (Supabase has this pre-installed)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column to page_analyses
-- Using 768 dimensions for Google's text-embedding-004 model
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS summary_embedding vector(768);

-- 3. Add embedding status to track generation progress
-- Values: 'pending', 'processing', 'completed', 'failed'
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS embedding_status TEXT DEFAULT 'pending';

-- 4. Add timestamp for when embedding was generated
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMP WITH TIME ZONE;

-- 5. Create index for vector similarity search
-- Using HNSW for accurate nearest neighbor search
-- HNSW is more accurate than IVFFlat, especially with varying data sizes
CREATE INDEX IF NOT EXISTS idx_page_analyses_embedding 
ON page_analyses 
USING hnsw (summary_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 6. Create index for finding pages without embeddings (for background job)
CREATE INDEX IF NOT EXISTS idx_page_analyses_embedding_status 
ON page_analyses (embedding_status) 
WHERE embedding_status != 'completed';

-- 7. Create a function for vector similarity search
-- This function searches by vector similarity and returns matching pages
CREATE OR REPLACE FUNCTION search_pages_by_embedding(
    p_user_id UUID,
    p_query_embedding vector(768),
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    page_number INT,
    summary TEXT,
    key_terms TEXT[],
    material_id UUID,
    material_name TEXT,
    course_id UUID,
    course_title TEXT,
    course_color TEXT,
    similarity FLOAT
) 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pa.id,
        pa.page_number,
        pa.summary,
        pa.key_terms,
        cm.id as material_id,
        cm.file_name as material_name,
        c.id as course_id,
        c.title as course_title,
        c.color_code as course_color,
        1 - (pa.summary_embedding <=> p_query_embedding) as similarity
    FROM page_analyses pa
    JOIN course_materials cm ON pa.course_material_id = cm.id
    JOIN courses c ON cm.course_id = c.id
    WHERE pa.user_id = p_user_id
      AND pa.summary_embedding IS NOT NULL
      AND pa.embedding_status = 'completed'
    ORDER BY pa.summary_embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$;

-- 8. Grant execute permission
GRANT EXECUTE ON FUNCTION search_pages_by_embedding TO authenticated;

-- 9. Add comment for documentation
COMMENT ON COLUMN page_analyses.summary_embedding IS 
    'Vector embedding of the page summary for semantic search. Generated using Google text-embedding-004 (768 dimensions).';

COMMENT ON COLUMN page_analyses.embedding_status IS 
    'Status of embedding generation: pending, processing, completed, or failed.';

COMMENT ON FUNCTION search_pages_by_embedding IS 
    'Search pages by vector similarity. Returns pages with their similarity score (0-1, higher is better).';
