-- Add deduplicate_flashcards setting to courses table
-- When enabled, flashcard generation will compare new cards against existing
-- cards in the course and remove duplicates with >85% similarity

ALTER TABLE courses ADD COLUMN deduplicate_flashcards BOOLEAN DEFAULT false;

COMMENT ON COLUMN courses.deduplicate_flashcards IS 'Enable course-wide deduplication when generating flashcards';
