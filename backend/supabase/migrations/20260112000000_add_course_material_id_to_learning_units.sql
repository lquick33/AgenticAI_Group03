-- ============================================================================
-- Migration: Add course_material_id to learning_units
-- ============================================================================
-- 
-- This migration adds a foreign key relationship from learning_units to 
-- course_materials, allowing learning units to be associated with specific
-- course materials (lectures/documents) rather than just courses.
--
-- Relationship structure:
--   Course → course_materials → learning_units
--   Course → course_materials → page_analyses
-- ============================================================================

-- Add course_material_id column (nullable to allow existing records)
ALTER TABLE learning_units
ADD COLUMN course_material_id UUID REFERENCES course_materials(id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX idx_learning_units_course_material ON learning_units(course_material_id);

-- Update RLS policy if needed (existing policy should still work)
-- The existing policy checks user_id, which is still required

-- Note: Existing learning_units will have course_material_id = NULL
-- This is acceptable as they can still be associated with courses via course_id
