-- Add chapter heading detection fields to page_analyses
-- Used for fast two-tier search: first search chapter headings, then fallback to full search

-- Add new columns for chapter heading detection
ALTER TABLE page_analyses 
ADD COLUMN IF NOT EXISTS is_chapter_heading BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS chapter_title TEXT;

-- Create partial index for fast chapter heading lookups
-- Only indexes rows where is_chapter_heading is true (small subset of all pages)
CREATE INDEX IF NOT EXISTS idx_page_analyses_chapter_headings 
ON page_analyses(user_id, is_chapter_heading) 
WHERE is_chapter_heading = TRUE;

-- Index for searching chapter titles with ILIKE
CREATE INDEX IF NOT EXISTS idx_page_analyses_chapter_title 
ON page_analyses(user_id, chapter_title) 
WHERE chapter_title IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN page_analyses.is_chapter_heading IS 'True if this page is a chapter/section title slide';
COMMENT ON COLUMN page_analyses.chapter_title IS 'The chapter title text if is_chapter_heading is true';
