-- Add has_flashcards column to course_materials for instant flashcard status display
-- This eliminates the need for separate API calls to check flashcard existence

ALTER TABLE course_materials
ADD COLUMN has_flashcards BOOLEAN DEFAULT FALSE NOT NULL;

-- Backfill existing data based on flashcard_cache
-- Set has_flashcards = TRUE for materials that have cached flashcards
UPDATE course_materials cm
SET has_flashcards = TRUE
WHERE EXISTS (
  SELECT 1 FROM flashcard_cache fc
  JOIN courses c ON c.id = cm.course_id
  WHERE fc.user_id = cm.user_id
  AND fc.deck_name = c.title || '::' || REPLACE(cm.file_name, '.pdf', '')
);

-- Add index for potential queries filtering by flashcard status
CREATE INDEX idx_course_materials_has_flashcards ON course_materials(user_id, has_flashcards);

COMMENT ON COLUMN course_materials.has_flashcards IS 'Whether flashcards have been generated for this material. Updated automatically when flashcards are generated.';
