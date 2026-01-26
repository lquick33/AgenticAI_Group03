-- Create table for slide snippets (user-created image crops from slides)
CREATE TABLE IF NOT EXISTS slide_snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_material_id UUID NOT NULL REFERENCES course_materials(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ensure one snippet per user per page per material
    CONSTRAINT idx_slide_snippets_material_page_user UNIQUE (course_material_id, page_number, user_id)
);

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_slide_snippets_material_id ON slide_snippets(course_material_id);
CREATE INDEX IF NOT EXISTS idx_slide_snippets_user_id ON slide_snippets(user_id);

-- Enable Row Level Security
ALTER TABLE slide_snippets ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Users can view their own snippets
CREATE POLICY "Users can view their own snippets" 
ON slide_snippets FOR SELECT 
USING (auth.uid() = user_id);

-- Users can insert their own snippets
CREATE POLICY "Users can insert their own snippets" 
ON slide_snippets FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Users can update their own snippets
CREATE POLICY "Users can update their own snippets" 
ON slide_snippets FOR UPDATE 
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Users can delete their own snippets
CREATE POLICY "Users can delete their own snippets" 
ON slide_snippets FOR DELETE 
USING (auth.uid() = user_id);

-- Storage bucket 'course_materials' is already configured, we will use it.
-- Path convention: snippets/{user_id}/{material_id}/page_{page_num}_{timestamp}.png
-- Existing storage policies should cover this if they are broad enough (usually based on user folder).
