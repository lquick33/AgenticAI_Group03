-- Migration: Add atomic insert for slide snippets
-- Automatically sets order_index based on the largest existing order_index for a specific page, solving race conditions on concurrent uploads.
-- Execute this script in your Supabase SQL Editor.

CREATE OR REPLACE FUNCTION insert_slide_snippet(
    p_course_material_id UUID,
    p_user_id UUID,
    p_page_number INTEGER,
    p_image_path TEXT
) RETURNS SETOF slide_snippets AS $$
BEGIN
    RETURN QUERY
    INSERT INTO slide_snippets (course_material_id, user_id, page_number, image_path, order_index)
    SELECT 
        p_course_material_id, 
        p_user_id, 
        p_page_number, 
        p_image_path, 
        COALESCE(MAX(order_index) + 1, 0)
    FROM slide_snippets
    WHERE course_material_id = p_course_material_id 
      AND page_number = p_page_number
    RETURNING *;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
