-- ============================================================================
-- Migration: Add classification columns to course_materials
-- ============================================================================
--
-- This migration adds classification support to the course_materials table.
-- Classification is generated on-demand when generating flashcards and stored
-- for future use.
--
-- Fields:
-- - classification: Enum type for material category
-- - classification_confidence: Confidence score (0.0-1.0)
-- - classification_reasoning: LLM reasoning for the classification
-- - classification_override: Whether this is a manual override
-- ============================================================================

-- Create enum type for material classification
CREATE TYPE material_classification_enum AS ENUM (
    'language_learning',
    'math',
    'business_administration',
    'general'
);

-- Add classification columns to course_materials table
ALTER TABLE course_materials
ADD COLUMN classification material_classification_enum,
ADD COLUMN classification_confidence FLOAT,
ADD COLUMN classification_reasoning TEXT,
ADD COLUMN classification_override BOOLEAN DEFAULT FALSE;

-- Add index for querying by classification
CREATE INDEX idx_course_materials_classification 
ON course_materials(classification) 
WHERE classification IS NOT NULL;
