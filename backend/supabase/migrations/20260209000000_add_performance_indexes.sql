-- ============================================================================
-- Performance Indexes Migration
-- Adds composite indexes for common query patterns
-- 
-- This migration is SAFE - adding indexes doesn't break existing queries,
-- it only makes them faster.
--
-- ROLLBACK: DROP INDEX IF EXISTS <index_name>;
-- ============================================================================

-- 1. Course materials lookup by user+course (used in list views)
-- Existing: idx_materials_course ON course_materials(course_id)
-- This adds user_id to the composite for faster filtered queries
CREATE INDEX IF NOT EXISTS idx_course_materials_user_course 
    ON course_materials(user_id, course_id);

-- 2. Messages by context page (for batch queries like get_messages_for_pages_batch)
-- Partial index only on non-null values for efficiency
CREATE INDEX IF NOT EXISTS idx_messages_context_page 
    ON messages(context_page_id) 
    WHERE context_page_id IS NOT NULL;

-- 3. Page analyses by user for course-wide searches
-- Useful for get_all_page_analyses_for_user type queries
CREATE INDEX IF NOT EXISTS idx_page_analyses_user_material 
    ON page_analyses(user_id, course_material_id);

-- 4. Conversations lookup by course (for study session queries)
CREATE INDEX IF NOT EXISTS idx_conversations_course 
    ON conversations(course_id) 
    WHERE course_id IS NOT NULL;

-- Note: The following indexes already exist and are NOT recreated:
-- - idx_analyses_lookup ON page_analyses(course_material_id, page_number) [initial_schema]
-- - idx_flashcard_cache_user_deck ON flashcard_cache(user_id, deck_name) [flashcard_anki_cache]
-- - idx_flashcard_cache_deck_pattern ON flashcard_cache(user_id, deck_name text_pattern_ops) [flashcard_anki_cache]
