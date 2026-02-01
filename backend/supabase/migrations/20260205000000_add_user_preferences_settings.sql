-- Migration: Add settings columns to user_preferences
-- This migration adds new columns for global user settings

-- Add default_deduplicate_flashcards column
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS default_deduplicate_flashcards BOOLEAN DEFAULT false;

-- Add theme_preference column
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS theme_preference TEXT DEFAULT 'system' 
CHECK (theme_preference IN ('light', 'dark', 'system'));

-- Add ankiweb_username column (placeholder for future AnkiWeb integration)
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS ankiweb_username TEXT;

-- Add comment for documentation
COMMENT ON COLUMN user_preferences.default_deduplicate_flashcards IS 'Default setting for flashcard deduplication when creating new courses';
COMMENT ON COLUMN user_preferences.theme_preference IS 'User preferred theme: light, dark, or system';
COMMENT ON COLUMN user_preferences.ankiweb_username IS 'AnkiWeb username for future sync integration';
