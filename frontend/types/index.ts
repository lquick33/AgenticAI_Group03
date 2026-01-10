// Database Types (matching Supabase schema)
export interface Profile {
  id: string
  email: string
  created_at: string
  updated_at: string
  google_calendar_token?: string | null
  google_calendar_refresh_token?: string | null
}

export interface UserPreferences {
  id: string
  user_id: string
  learning_style: 'linear' | 'iterative'
  agent_persona: 'strict' | 'humorous' | 'buddy'
  preferred_study_times: string[]
  created_at: string
  updated_at: string
}

export interface Course {
  id: string
  user_id: string
  title: string
  description?: string | null
  exam_date?: string | null
  created_at: string
  updated_at: string
}

export interface CourseMaterial {
  id: string
  course_id: string
  file_name: string
  file_path: string
  file_type: 'pdf' | 'pptx' | 'md' | 'txt'
  page_count: number
  uploaded_at: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
}

export interface PageAnalysis {
  id: string
  course_material_id: string
  page_number: number
  analysis_data: {
    summary: string
    key_terms: string[]
    exam_questions: string[]
    diagram_descriptions?: string
  }
  image_path?: string | null
  created_at: string
  updated_at: string
}

export interface LearningUnit {
  id: string
  course_id: string
  topic_name: string
  planned_date: string
  planned_time: string
  actual_date?: string | null
  actual_time?: string | null
  status: 'planned' | 'completed' | 'skipped' | 'rescheduled'
  comprehension_score?: number | null
  notes?: string | null
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  user_id: string
  course_id?: string | null
  session_type: 'study' | 'planning' | 'general'
  started_at: string
  ended_at?: string | null
  metadata?: Record<string, unknown>
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  page_number?: number | null
  created_at: string
}

export interface Flashcard {
  id: string
  course_id: string
  front: string
  back: string
  page_number?: number | null
  created_at: string
}
