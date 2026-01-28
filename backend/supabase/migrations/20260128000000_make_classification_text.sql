-- ============================================================================
-- Migration: Make course_materials.classification a flexible text column
-- ============================================================================
--
-- This migration changes the classification column from the
-- material_classification_enum enum type to TEXT, so that new
-- classification labels (e.g. 'computer_science') can be added
-- without further schema changes.
--
-- NOTE: This migration preserves all existing data by casting the
-- enum values to text. No row data is deleted.
-- ============================================================================

-- Change classification column type from enum to text, preserving data
ALTER TABLE course_materials
ALTER COLUMN classification TYPE TEXT USING classification::TEXT;

-- Optionally drop the enum type if it is no longer used elsewhere.
-- This removes the type definition but does NOT delete any table data.
DROP TYPE IF EXISTS material_classification_enum;

