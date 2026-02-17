-- ============================================================================
-- Knowledge Tracking Migration
-- Adds tables for tracking Anki deck knowledge levels per user
-- ============================================================================

-- 1. Course-to-Deck Mappings
-- Maps courses and course_materials to Anki deck names
CREATE TABLE IF NOT EXISTS course_deck_mappings (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
    course_material_id UUID REFERENCES course_materials(id) ON DELETE CASCADE,
    
    deck_name TEXT NOT NULL,  -- e.g., "Marketing 101::Lecture 1 - Introduction"
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    -- One deck mapping per user per deck name
    UNIQUE(user_id, deck_name)
);

-- Index for querying all decks for a course
CREATE INDEX IF NOT EXISTS idx_deck_mapping_course ON course_deck_mappings(course_id);
CREATE INDEX IF NOT EXISTS idx_deck_mapping_user ON course_deck_mappings(user_id);

-- 2. Deck Knowledge Snapshots
-- Stores periodic snapshots of knowledge levels for trend analysis
CREATE TABLE IF NOT EXISTS deck_knowledge_snapshots (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    deck_name TEXT NOT NULL,
    
    -- Optional links to course structure for faster queries
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    course_material_id UUID REFERENCES course_materials(id) ON DELETE SET NULL,
    
    -- Card counts
    total_cards INT NOT NULL DEFAULT 0,
    new_cards INT NOT NULL DEFAULT 0,
    learning_cards INT NOT NULL DEFAULT 0,
    young_cards INT NOT NULL DEFAULT 0,      -- Review queue, interval < 21 days
    mature_cards INT NOT NULL DEFAULT 0,     -- Review queue, interval >= 21 days
    suspended_cards INT DEFAULT 0,
    
    -- Aggregate metrics
    avg_ease_factor FLOAT,
    avg_interval_days FLOAT,
    retention_rate FLOAT,          -- 1 - (lapses/reviews)
    mastery_score FLOAT,           -- Composite 0.0-1.0
    
    -- Review activity (optional, for trend analysis)
    reviews_last_7_days INT DEFAULT 0,
    reviews_last_30_days INT DEFAULT 0,
    
    -- When this snapshot was captured
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_knowledge_user_deck ON deck_knowledge_snapshots(user_id, deck_name, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_course ON deck_knowledge_snapshots(course_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_captured ON deck_knowledge_snapshots(captured_at DESC);

-- 3. Anki Card Mappings
-- Links agent-generated flashcards to Anki note IDs for tracking
CREATE TABLE IF NOT EXISTS anki_card_mappings (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    flashcard_id UUID REFERENCES flashcards(id) ON DELETE CASCADE,
    anki_note_id BIGINT NOT NULL,
    deck_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    -- One mapping per user per Anki note
    UNIQUE(user_id, anki_note_id)
);

CREATE INDEX IF NOT EXISTS idx_anki_mapping_flashcard ON anki_card_mappings(flashcard_id);
CREATE INDEX IF NOT EXISTS idx_anki_mapping_user ON anki_card_mappings(user_id);

-- 4. Enable RLS on new tables
ALTER TABLE course_deck_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE deck_knowledge_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE anki_card_mappings ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies - Users can only see/modify their own data
CREATE POLICY "Users can CRUD own deck mappings" 
    ON course_deck_mappings FOR ALL 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own knowledge snapshots" 
    ON deck_knowledge_snapshots FOR ALL 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can CRUD own anki mappings" 
    ON anki_card_mappings FOR ALL 
    USING (auth.uid() = user_id);
