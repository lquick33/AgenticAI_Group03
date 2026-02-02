-- Migration: Add auto_explain_on_page_change setting to user_preferences
-- This allows users to control whether the AI tutor automatically explains content on page changes

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS auto_explain_on_page_change BOOLEAN DEFAULT true;

-- Add comment for documentation
COMMENT ON COLUMN user_preferences.auto_explain_on_page_change IS 'When true, AI tutor automatically explains content when user navigates to a new page. When false, AI only responds to user messages.';
