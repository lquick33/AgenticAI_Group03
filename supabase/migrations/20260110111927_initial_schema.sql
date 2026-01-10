-- ============================================================================
-- Lernkompanien Database Schema
-- Initial Migration: Complete schema setup for vision-first multimodal approach
-- ============================================================================

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. ENUM Types (Domänenspezifische Werte)
CREATE TYPE learning_style_enum AS ENUM ('linear', 'iterative');
CREATE TYPE agent_persona_enum AS ENUM ('strict', 'humorous', 'buddy');
CREATE TYPE unit_status_enum AS ENUM ('planned', 'completed', 'skipped', 'rescheduled');
CREATE TYPE file_status_enum AS ENUM ('uploading', 'processing', 'completed', 'error');
CREATE TYPE sender_role_enum AS ENUM ('user', 'assistant', 'system');
CREATE TYPE session_type_enum AS ENUM ('study', 'planning', 'general');

-- 3. Tabellen

-- A. User Profiles (Erweitert auth.users)
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT,
  avatar_url TEXT,
  google_calendar_token TEXT, -- Encrypted storing recommended in app logic
  google_calendar_refresh_token TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- B. User Preferences (Onboarding Quiz & Settings)
CREATE TABLE user_preferences (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL UNIQUE,
  learning_style learning_style_enum DEFAULT 'linear',
  agent_persona agent_persona_enum DEFAULT 'buddy',
  preferred_study_times JSONB, -- z.B. {"mon": ["18:00", "20:00"], "tue": ...}
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- C. Courses (Fächer/Module)
CREATE TABLE courses (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  title TEXT NOT NULL, -- z.B. "Marketing 101"
  description TEXT,
  exam_date DATE,
  color_code TEXT DEFAULT '#3b82f6', -- Für UI/Kalender
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- D. Course Materials (Die Dateien: PDF, PPTX)
CREATE TABLE course_materials (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL, -- Redundanz für einfachere RLS
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL, -- Pfad im Supabase Storage Bucket
  file_type TEXT NOT NULL, -- 'pdf', 'pptx'
  page_count INT DEFAULT 0,
  processing_status file_status_enum DEFAULT 'uploading',
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- E. Page Analyses (DAS HERZSTÜCK - Multimodal Output)
-- Hier landet das Ergebnis von GPT-4o Vision pro Seite
CREATE TABLE page_analyses (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  course_material_id UUID REFERENCES course_materials(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL, -- RLS Helper
  page_number INT NOT NULL,
  
  -- Strukturierte Analyse-Daten
  summary TEXT,               -- Zusammenfassung der Seite
  key_terms TEXT[],           -- Array von wichtigen Begriffen
  exam_questions TEXT[],      -- Array möglicher Prüfungsfragen
  diagram_description TEXT,   -- Beschreibung visueller Elemente
  
  -- Backup des kompletten JSONs vom LLM
  raw_analysis JSONB, 
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  
  -- Constraint: Eine Analyse pro Seite pro Datei
  UNIQUE(course_material_id, page_number)
);

-- F. Learning Units (Kalender-Events)
CREATE TABLE learning_units (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  
  title TEXT NOT NULL, -- Thema der Session
  description TEXT,
  
  -- Zeitplanung
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  end_time TIMESTAMP WITH TIME ZONE NOT NULL,
  duration_minutes INT GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (end_time - start_time))/60) STORED,
  
  -- Status & Sync
  status unit_status_enum DEFAULT 'planned',
  google_calendar_event_id TEXT, -- Zum Matchen mit Google Cal
  
  -- Ergebnis
  comprehension_score FLOAT, -- 0.0 bis 1.0 (Feedback vom Supervisor)
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- G. Flashcards (Karteikarten)
CREATE TABLE flashcards (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  source_page_analysis_id UUID REFERENCES page_analyses(id) ON DELETE SET NULL, -- Link zur Quelle
  
  front TEXT NOT NULL,
  back TEXT NOT NULL,
  
  -- Spaced Repetition Felder (Optional für später)
  next_review_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
  interval INT DEFAULT 1,
  ease_factor FLOAT DEFAULT 2.5,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- H. Chat Conversations
CREATE TABLE conversations (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  course_id UUID REFERENCES courses(id) ON DELETE CASCADE, -- Optional: Chat kann kursgebunden sein
  title TEXT DEFAULT 'New Chat',
  session_type session_type_enum DEFAULT 'general', -- 'study', 'planning', 'general'
  metadata JSONB, -- e.g., {"current_page": 5, "topic": "Statistics"}
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- I. Messages
CREATE TABLE messages (
  id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE NOT NULL,
  role sender_role_enum NOT NULL,
  content TEXT NOT NULL,
  
  -- Kontext: Auf welcher Seite war der User gerade?
  context_page_id UUID REFERENCES page_analyses(id) ON DELETE SET NULL,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Indexes (Performance)
CREATE INDEX idx_materials_course ON course_materials(course_id);
CREATE INDEX idx_analyses_lookup ON page_analyses(course_material_id, page_number);
CREATE INDEX idx_units_user_date ON learning_units(user_id, start_time);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- 5. Row Level Security (RLS) aktivieren
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_materials ENABLE ROW LEVEL SECURITY;
ALTER TABLE page_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- 6. RLS Policies (Vereinfacht: User sieht nur seine Daten)

-- Helper Funktion um Code zu sparen
CREATE OR REPLACE FUNCTION auth_uid() 
RETURNS uuid 
LANGUAGE sql STABLE 
AS $$ 
  SELECT auth.uid(); 
$$;

-- Policy Templates (Wiederholen für alle Tabellen)
CREATE POLICY "Users can CRUD own profiles" ON profiles FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users can CRUD own preferences" ON user_preferences FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can CRUD own courses" ON courses FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can CRUD own materials" ON course_materials FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can CRUD own analyses" ON page_analyses FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can CRUD own units" ON learning_units FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can CRUD own flashcards" ON flashcards FOR ALL USING (auth.uid() = user_id);

-- Für Conversations & Messages ist es etwas komplexer (Join via User), 
-- aber wenn user_id in conversation ist, reicht das:
CREATE POLICY "Users can CRUD own conversations" ON conversations FOR ALL USING (auth.uid() = user_id);

-- Messages checken Conversation owner
CREATE POLICY "Users can CRUD own messages" ON messages FOR ALL USING (
  EXISTS (
    SELECT 1 FROM conversations c 
    WHERE c.id = messages.conversation_id 
    AND c.user_id = auth.uid()
  )
);

-- 7. Automatische `updated_at` Trigger Funktion
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger anwenden
CREATE TRIGGER update_profiles_modtime BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_preferences_modtime BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_courses_modtime BEFORE UPDATE ON courses FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_units_modtime BEFORE UPDATE ON learning_units FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_conversations_modtime BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- 8. Storage Bucket Setup
-- Note: Bucket creation often needs to be done via Dashboard, but we try here
INSERT INTO storage.buckets (id, name, public) 
VALUES ('course_materials', 'course_materials', false) 
ON CONFLICT (id) DO NOTHING;

-- Storage Policies: Nur eigene Dateien sehen/hochladen/löschen
-- File structure: {user_id}/{course_id}/{filename}
CREATE POLICY "User can upload own materials" 
ON storage.objects FOR INSERT 
TO authenticated 
WITH CHECK (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "User can select own materials" 
ON storage.objects FOR SELECT 
TO authenticated 
USING (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "User can update own materials" 
ON storage.objects FOR UPDATE 
TO authenticated 
USING (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "User can delete own materials" 
ON storage.objects FOR DELETE 
TO authenticated 
USING (
  bucket_id = 'course_materials' 
  AND (storage.foldername(name))[1] = auth.uid()::text
);
