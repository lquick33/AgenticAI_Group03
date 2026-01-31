-- ============================================================================
-- Anki Study History Migration
-- Stores daily study statistics from Anki for dashboard charts
-- ============================================================================

-- 1. Create the anki_study_history table
CREATE TABLE IF NOT EXISTS anki_study_history (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
    
    -- The study date (one row per user per day)
    study_date DATE NOT NULL,
    
    -- Core metrics
    cards_reviewed INT NOT NULL DEFAULT 0,          -- Total number of reviews
    time_spent_seconds INT NOT NULL DEFAULT 0,      -- Total study time in seconds
    
    -- Button press breakdown (1=Again, 2=Hard, 3=Good, 4=Easy)
    again_count INT NOT NULL DEFAULT 0,             -- "Again" presses (forgotten)
    hard_count INT NOT NULL DEFAULT 0,              -- "Hard" presses
    good_count INT NOT NULL DEFAULT 0,              -- "Good" presses
    easy_count INT NOT NULL DEFAULT 0,              -- "Easy" presses
    
    -- Card type breakdown
    new_cards INT NOT NULL DEFAULT 0,               -- First-time learning (type=0)
    review_cards INT NOT NULL DEFAULT 0,            -- Regular reviews (type=1)
    relearn_cards INT NOT NULL DEFAULT 0,           -- Relearning after lapse (type=2)
    
    -- Derived metrics
    avg_time_per_card_ms INT NOT NULL DEFAULT 0,    -- Average time per review (ms)
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    -- One row per user per day
    UNIQUE(user_id, study_date)
);

-- 2. Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_study_history_user_date 
    ON anki_study_history(user_id, study_date DESC);

CREATE INDEX IF NOT EXISTS idx_study_history_date 
    ON anki_study_history(study_date DESC);

-- 3. Enable Row Level Security
ALTER TABLE anki_study_history ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policy - Users can only see/modify their own data
CREATE POLICY "Users can CRUD own study history" 
    ON anki_study_history FOR ALL 
    USING (auth.uid() = user_id);

-- 5. Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_study_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_study_history_updated_at
    BEFORE UPDATE ON anki_study_history
    FOR EACH ROW
    EXECUTE FUNCTION update_study_history_updated_at();
