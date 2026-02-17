-- Migration: Add Full-Text Search to page_analyses
-- Purpose: Enable multilingual (German + English) full-text search for Quick Chat topic finder
-- Date: 2026-02-07

-- Enable unaccent extension for accent-insensitive search
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Create immutable unaccent function for use in generated columns
-- (Regular unaccent is not immutable, which is required for generated columns)
CREATE OR REPLACE FUNCTION immutable_unaccent(text)
RETURNS text AS $$
  SELECT public.unaccent('public.unaccent', $1)
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE STRICT;

-- Add tsvector column for German full-text search
-- Weights: A = summary (most important), B = key_terms
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS search_vector_de tsvector
GENERATED ALWAYS AS (
  setweight(to_tsvector('german', immutable_unaccent(coalesce(summary, ''))), 'A') ||
  setweight(to_tsvector('german', immutable_unaccent(coalesce(array_to_string(key_terms, ' '), ''))), 'B')
) STORED;

-- Add tsvector column for English full-text search
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS search_vector_en tsvector
GENERATED ALWAYS AS (
  setweight(to_tsvector('english', immutable_unaccent(coalesce(summary, ''))), 'A') ||
  setweight(to_tsvector('english', immutable_unaccent(coalesce(array_to_string(key_terms, ' '), ''))), 'B')
) STORED;

-- Create GIN indexes for fast full-text search
CREATE INDEX IF NOT EXISTS idx_page_analyses_search_de 
ON page_analyses USING GIN (search_vector_de);

CREATE INDEX IF NOT EXISTS idx_page_analyses_search_en 
ON page_analyses USING GIN (search_vector_en);

-- Add composite index for user_id + search to optimize user-scoped searches
CREATE INDEX IF NOT EXISTS idx_page_analyses_user_search_de
ON page_analyses USING GIN (search_vector_de) WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_page_analyses_user_search_en
ON page_analyses USING GIN (search_vector_en) WHERE user_id IS NOT NULL;

-- Comment on columns for documentation
COMMENT ON COLUMN page_analyses.search_vector_de IS 'German full-text search vector (auto-generated from summary + key_terms)';
COMMENT ON COLUMN page_analyses.search_vector_en IS 'English full-text search vector (auto-generated from summary + key_terms)';
