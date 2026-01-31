-- ============================================================================
-- Add AnkiWeb Sync Tracking to Flashcard Cache
-- Tracks which cards have been synced to AnkiWeb for retry functionality
-- 
-- ROLLBACK: 
--   ALTER TABLE flashcard_cache DROP COLUMN IF EXISTS synced_to_ankiweb;
--   DROP INDEX IF EXISTS idx_flashcard_cache_unsynced;
-- ============================================================================

-- 1. Add synced_to_ankiweb column to track AnkiWeb sync status
-- Default FALSE since existing cards may not have been synced
ALTER TABLE flashcard_cache 
ADD COLUMN IF NOT EXISTS synced_to_ankiweb BOOLEAN DEFAULT FALSE;

-- 2. Add index for efficiently querying unsynced cards
-- Partial index only includes unsynced cards for fast retry queries
CREATE INDEX IF NOT EXISTS idx_flashcard_cache_unsynced 
ON flashcard_cache(user_id, synced_to_ankiweb) 
WHERE synced_to_ankiweb = FALSE;

-- 3. Add comment for documentation
COMMENT ON COLUMN flashcard_cache.synced_to_ankiweb IS 
    'Whether this card has been synced to AnkiWeb. FALSE means sync pending.';
