-- ============================================================================
-- Flashcard Anki Cache Migration (SAFE - Additive Only)
-- Adds Anki-aligned cache table alongside existing flashcards table
-- 
-- This migration:
-- 1. Creates the new flashcard_cache table
-- 2. KEEPS the old flashcards table (for rollback safety)
-- 
-- ROLLBACK: Simply DROP TABLE flashcard_cache;
-- FINALIZE: After testing, run: DROP TABLE flashcards CASCADE;
-- ============================================================================

-- 1. Create new flashcard_cache table (Anki-aligned)
CREATE TABLE IF NOT EXISTS flashcard_cache (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    
    -- Anki identifiers (source of truth)
    anki_note_id BIGINT NOT NULL,
    deck_name TEXT NOT NULL,              -- "Course::Lecture" hierarchy
    
    -- Content (cached from Anki)
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    tags TEXT[],                          -- Includes page:N, source:uuid, topic tags
    
    -- Anki metadata
    anki_mod BIGINT,                      -- Anki's modification timestamp for sync detection
    
    -- Optional: Denormalized DB reference (for faster joins)
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    
    -- Timestamps
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- One cache entry per user per Anki note
    UNIQUE(user_id, anki_note_id)
);

-- 2. Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_flashcard_cache_user_deck 
    ON flashcard_cache(user_id, deck_name);

CREATE INDEX IF NOT EXISTS idx_flashcard_cache_course 
    ON flashcard_cache(course_id) 
    WHERE course_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_flashcard_cache_deck_pattern 
    ON flashcard_cache(user_id, deck_name text_pattern_ops);

-- 3. Enable RLS
ALTER TABLE flashcard_cache ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policy - Users can only see/modify their own cache
CREATE POLICY "Users can CRUD own flashcard cache" 
    ON flashcard_cache FOR ALL 
    USING (auth.uid() = user_id);

-- 5. OLD: Drop flashcards table (COMMENTED OUT FOR SAFETY)
-- Run this manually AFTER extensive testing confirms the new system works:
-- DROP TABLE IF EXISTS flashcards CASCADE;

-- 6. Helper function to extract source UUID from tags
CREATE OR REPLACE FUNCTION extract_source_from_tags(tags TEXT[])
RETURNS TEXT AS $$
DECLARE
    tag TEXT;
BEGIN
    FOREACH tag IN ARRAY COALESCE(tags, ARRAY[]::TEXT[])
    LOOP
        IF tag LIKE 'source:%' THEN
            RETURN SUBSTRING(tag FROM 8);
        END IF;
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 7. Helper function to extract page number from tags
CREATE OR REPLACE FUNCTION extract_page_from_tags(tags TEXT[])
RETURNS INTEGER AS $$
DECLARE
    tag TEXT;
BEGIN
    FOREACH tag IN ARRAY COALESCE(tags, ARRAY[]::TEXT[])
    LOOP
        IF tag LIKE 'page:%' THEN
            RETURN CAST(SUBSTRING(tag FROM 6) AS INTEGER);
        END IF;
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
