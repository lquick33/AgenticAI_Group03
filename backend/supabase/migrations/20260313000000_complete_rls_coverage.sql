-- ============================================================================
-- Migration: Add missing RLS policies
-- 
-- Description:
-- 1. Ensures Row Level Security is enabled on all tables missed in previous
--    migrations or where policies were incomplete.
-- 2. Hardens security for SaaS commercial readiness.
-- ============================================================================

-- 1. Check and enable RLS on all remaining tables if any are missing
ALTER TABLE IF EXISTS quiz_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quizzes ENABLE ROW LEVEL SECURITY;

-- 2. Add policies for quizzes
DO $$ 
BEGIN
    IF EXISTS (
        SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'quizzes'
    ) THEN
        DROP POLICY IF EXISTS "Users can CRUD own quizzes" ON quizzes;
        CREATE POLICY "Users can CRUD own quizzes" ON quizzes 
            FOR ALL USING (auth.uid() = user_id);
    END IF;

    IF EXISTS (
        SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = 'quiz_results'
    ) THEN
        DROP POLICY IF EXISTS "Users can CRUD own quiz results" ON quiz_results;
        CREATE POLICY "Users can CRUD own quiz results" ON quiz_results 
            FOR ALL USING (
              EXISTS (
                SELECT 1 FROM quizzes q 
                WHERE q.id = quiz_results.quiz_id 
                AND q.user_id = auth.uid()
              )
            );
    END IF;
END $$;

-- 3. Storage Bucket Policies Harden (course_materials)
-- We drop existing and recreate strictly
DROP POLICY IF EXISTS "User can upload own materials" ON storage.objects;
DROP POLICY IF EXISTS "User can select own materials" ON storage.objects;
DROP POLICY IF EXISTS "User can update own materials" ON storage.objects;
DROP POLICY IF EXISTS "User can delete own materials" ON storage.objects;

CREATE POLICY "Users can fully manage their own storage folders"
ON storage.objects FOR ALL
TO authenticated
USING (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Note: The core tables (profiles, courses, course_materials, page_analyses, 
-- learning_units, flashcards, conversations, messages, course_deck_mappings,
-- deck_knowledge_snapshots, anki_card_mappings, anki_study_history, flashcard_cache,
-- slide_snippets) already have solid `auth.uid() = user_id` policies defined
-- in their respective initial migration files.
