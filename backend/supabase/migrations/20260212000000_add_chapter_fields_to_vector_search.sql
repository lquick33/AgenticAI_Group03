-- Add is_chapter_heading and chapter_title to vector search RPC so intro-page scorer receives them.
-- Enables chapter_bonus in quickchat when a chapter/title page matches the query.
-- Must DROP first because PostgreSQL does not allow changing the return type with CREATE OR REPLACE.

DROP FUNCTION IF EXISTS search_pages_by_embedding(uuid, vector(768), integer);

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
    is_chapter_heading BOOLEAN,
    chapter_title TEXT,
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
        COALESCE(pa.is_chapter_heading, FALSE) as is_chapter_heading,
        pa.chapter_title,
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

GRANT EXECUTE ON FUNCTION search_pages_by_embedding TO authenticated;

COMMENT ON FUNCTION search_pages_by_embedding IS
    'Search pages by vector similarity. Returns pages with similarity score and chapter heading fields for intro-page scoring.';
