-- ============================================================================
-- Migration: Add summary column to course_materials
-- ============================================================================
--
-- This migration adds a TEXT column `summary` to the `course_materials` table.
-- The field is intended to store a JSON-encoded, LLM-generierte
-- Gesamtzusammenfassung einer Vorlesung (Kernthemen / Konzepte) pro Upload.
--
-- The summary is optional and will be populated asynchronously by the
-- background PDF processing pipeline after per-page analyses have completed.
-- ============================================================================

ALTER TABLE course_materials
ADD COLUMN summary TEXT;

