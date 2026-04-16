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
  default_deduplicate_flashcards?: boolean
  theme_preference?: 'light' | 'dark' | 'system'
  ankiweb_username?: string | null
  auto_explain_on_page_change?: boolean
  created_at: string
  updated_at: string
}

export interface Course {
  id: string
  user_id: string
  title: string
  description?: string | null
  exam_date?: string | null
  color_code?: string | null
  deduplicate_flashcards?: boolean
  created_at: string
  updated_at: string
}

export interface CourseWithStats extends Course {
  material_count: number
  analyzed_pages: number
  total_pages: number
  last_updated: string | null
}

export interface CourseMaterial {
  id: string
  course_id: string
  user_id: string
  file_name: string
  file_path: string
  file_type: 'pdf' | 'pptx' | 'md' | 'txt'
  page_count: number
  processing_status: 'uploading' | 'processing' | 'completed' | 'error'
  error_message?: string | null
  created_at: string
  summary?: string | null
  has_flashcards?: boolean
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
  course_material_id?: string | null
  user_id: string
  title: string
  description?: string | null
  start_time: string
  end_time: string
  duration_minutes?: number
  status: 'planned' | 'completed' | 'skipped' | 'rescheduled'
  google_calendar_event_id?: string | null
  comprehension_score?: number | null
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

export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  result?: string
  state?: 'pending' | 'running' | 'completed' | 'error'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  toolCalls?: ToolCall[]
  quiz?: {
    quiz_id: string
    topic: string
    questions: QuizQuestion[]
  }
}

export interface PageAnalysisData {
  summary: string
  key_terms: string[]
  exam_questions: string[]
  diagram_description?: string
}

// Quiz-related types

export interface QuizQuestion {
  id: string
  question: string
  options: Record<'A' | 'B' | 'C' | 'D', string>
  correct_answer: 'A' | 'B' | 'C' | 'D'
  difficulty: 'easy' | 'medium' | 'hard'
  explanation: string
}

export interface QuizToolResponse {
  quiz_id: string
  quiz_data: QuizData
  topic: string
  question_count: number
  start_page: number
  end_page: number
}

export enum QuizState {
  PENDING = 'pending',
  CREATING = 'creating',
  READY = 'ready',
  COMPLETED = 'completed',
  ERROR = 'error'
}

export type ToolResponseEvent = 
  | { type: 'tool_call'; tool_calls: ToolCall[]; message_id: string }
  | { type: 'tool_response'; tool_call_id: string; result: string; message_id: string }
  | { type: 'delta'; role: 'assistant'; delta: string; content: string }
  | { type: 'error'; error: string }

export interface QuizData {
  topic: string
  questions: QuizQuestion[]
  metadata?: {
    easy_count?: number
    medium_count?: number
    hard_count?: number
  }
}

export interface Quiz {
  id: string
  course_material_id: string
  user_id: string
  topic_name: string
  start_page: number
  end_page: number
  quiz_data: QuizData
  created_at: string
}

export interface QuizAnswer {
  question_id: string
  answer: 'A' | 'B' | 'C' | 'D'
}

export interface QuestionResult {
  question_id: string
  user_answer: 'A' | 'B' | 'C' | 'D'
  correct_answer: 'A' | 'B' | 'C' | 'D'
  correct: boolean
  explanation?: string | null
}

export interface QuizResult {
  quiz_id: string
  score: number // 0.0 to 1.0
  correct_count: number
  total_questions: number
  question_results: QuestionResult[]
  completed_at: string
  tutor_feedback?: string | null
}

