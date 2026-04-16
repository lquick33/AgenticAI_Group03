/**
 * API Client Functions for Study Session
 * 
 * Handles communication with the backend API for:
 * - Chat initiation and messaging
 * - Page analysis retrieval
 * - SSE streaming
 */

import type { ChatMessage, Flashcard, PageAnalysisData, ToolCall, QuizResult } from '@/types'
import { getApiUrl } from '@/lib/public-env'

const API_URL = getApiUrl()
export interface StudyStreamMessage {
  role: string
  content: unknown
}

export interface StudyStreamChunk {
  [key: string]: unknown
  node?: string
  messages?: StudyStreamMessage[]
  type?: string
  delta?: string
  content?: string
  role?: string
  error?: string
  tool_calls?: ToolCall[]
  tool_call_id?: string
  result?: string
  message_id?: string
}

/**
 * Parse SSE chunk to extract message data
 * Supports both delta events, regular message chunks, and tool call events
 */
export function parseSSEChunk(chunk: string): StudyStreamChunk | null {
  if (chunk.trim() === '' || chunk === 'data: [DONE]') {
    return null
  }

  try {
    const data = chunk.replace(/^data: /, '')
    return JSON.parse(data)
  } catch (error) {
    console.error('Error parsing SSE chunk:', error)
    return null
  }
}

/**
 * Helper to process streaming responses
 */
function processStreamResponse(
  response: Response,
  onChunk: (chunk: StudyStreamChunk) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void
): { close: () => void; done: Promise<void> } {
  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let isClosed = false

  const donePromise = (async () => {
    try {
      while (!isClosed) {
        const { done, value } = await reader.read()

        if (done) {
          if (!isClosed) {
            isClosed = true
            onComplete?.()
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim()) {
            if (line.trim() === 'data: [DONE]') {
              if (!isClosed) {
                isClosed = true
                onComplete?.()
              }
              return
            }
            const chunk = parseSSEChunk(line)
            if (chunk) onChunk(chunk)
          }
        }
      }
    } catch (error) {
      if (!isClosed) {
        isClosed = true
        onError?.(error instanceof Error ? error : new Error(String(error)))
      }
    }
  })()

  return {
    close: () => {
      isClosed = true
      reader.cancel()
    },
    done: donePromise
  }
}

/**
 * Initiate a chat session for a study page
 */
export async function initiateChat(
  materialId: string,
  pageNumber: number,
  userId: string,
  onChunk: (chunk: StudyStreamChunk) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
  isInitialOpen: boolean = false
): Promise<{ close: () => void }> {
  const requestUrl = `${API_URL}/api/chat/initiate`;
  // Use fetch with POST and stream the response
  let response: Response;
  try {
    response = await fetch(requestUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      material_id: materialId,
      page_number: pageNumber,
      user_id: userId,
      is_initial_open: isInitialOpen,
    }),
    })
  } catch (fetchError) {
    throw fetchError;
  }


  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`)
  }

  const controller = processStreamResponse(response, onChunk, onComplete, onError)
  return { close: controller.close }
}

/**
 * Send a message in an existing chat session
 */
export function sendMessage(
  materialId: string,
  message: string,
  userId: string,
  onChunk: (chunk: StudyStreamChunk) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
  pageNumber?: number
): Promise<void> {
  return new Promise((resolve, reject) => {
    const body: Record<string, unknown> = {
      material_id: materialId,
      message,
      user_id: userId,
    }
    
    // Include page_number if provided
    if (pageNumber !== undefined) {
      body.page_number = pageNumber
    }
    
    fetch(`${API_URL}/api/chat/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
      .then(async (response) => {
        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: 'Request failed' }))
          throw new Error(error.detail || `HTTP ${response.status}`)
        }

        const controller = processStreamResponse(
          response, 
          onChunk, 
          onComplete, 
          (err) => {
            onError?.(err)
            reject(err)
          }
        )
        
        await controller.done
        resolve()
      })
      .catch((error) => {
        onError?.(error)
        reject(error)
      })
  })
}

/**
 * Get page analysis data
 */
export async function getPageAnalysis(
  courseMaterialId: string,
  pageNumber: number,
  userId: string
): Promise<PageAnalysisData> {
  const response = await fetch(
    `${API_URL}/api/page-analysis?course_material_id=${courseMaterialId}&page_number=${pageNumber}&user_id=${userId}`
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Load persisted study session (last page and chat history)
 */
export async function getStudySession(
  materialId: string,
  userId: string
): Promise<{ lastPage: number; messages: ChatMessage[] }> {
  const requestUrl = `${API_URL}/api/study/session?material_id=${encodeURIComponent(materialId)}&user_id=${encodeURIComponent(userId)}`;
  let response: Response;
  try {
    response = await fetch(requestUrl, {
      method: 'GET',
    })
  } catch (fetchError) {
    throw fetchError;
  }


  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`)
  }

  const data = await response.json()

  // Backend already returns messages in ChatMessage shape (id, role, content, timestamp)
  return {
    lastPage: data.lastPage ?? 1,
    messages: (data.messages || []) as ChatMessage[],
  }
}

/**
 * Save current page number for a study session
 * 
 * This lightweight function saves the user's current page without
 * triggering a full chat initiation. Used for page persistence.
 */
export async function saveCurrentPage(
  materialId: string,
  userId: string,
  page: number
): Promise<void> {
  try {
    const response = await fetch(`${API_URL}/api/study/save-page`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        material_id: materialId,
        user_id: userId,
        page,
      }),
    })

    if (!response.ok) {
      // Log error but don't throw - page save is best-effort
      console.error('[saveCurrentPage] Failed to save page:', response.status)
    }
  } catch (error) {
    // Log error but don't throw - page save is best-effort
    console.error('[saveCurrentPage] Error saving page:', error)
  }
}

/**
 * Flashcard generation task status
 */
export interface FlashcardTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  total_pages: number
  processed_pages: number
  cards_generated: number
  error_message?: string
  filename?: string
  anki_synced?: boolean  // Cards added to local Anki
  ankiweb_synced?: boolean  // Cards synced to AnkiWeb
  created_at: number
  completed_at?: number
}

/**
 * Start flashcard generation as a background task
 */
export async function generateFlashcards(
  materialId: string,
  userId: string,
  deduplicateCourse: boolean = false
): Promise<{ task_id: string; status: string; message: string }> {
  const params = new URLSearchParams({
    course_material_id: materialId,
    user_id: userId,
    deduplicate_course: String(deduplicateCourse),
  })
  const url = `${API_URL}/api/flashcards/generate?${params.toString()}`
  
  const response = await fetch(url, {
    method: 'POST',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Get flashcard generation task status
 */
export async function getFlashcardTaskStatus(
  taskId: string,
  userId: string
): Promise<FlashcardTaskStatus> {
  const url = `${API_URL}/api/flashcards/status/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Download generated flashcard .apkg file
 */
export async function downloadFlashcards(
  taskId: string,
  userId: string
): Promise<{ blob: Blob; filename: string }> {
  const url = `${API_URL}/api/flashcards/download/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  // Extract filename from Content-Disposition header
  const contentDisposition = response.headers.get('Content-Disposition')
  let filename = `flashcards_${taskId}.apkg`
  
  if (contentDisposition) {
    // Parse filename from header: attachment; filename="Course - Lecture.apkg"
    const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
    if (match && match[1]) {
      filename = match[1]
    }
  }

  const blob = await response.blob()
  return { blob, filename }
}

/**
 * Get flashcards for a course material from database
 */
export async function getFlashcardsForMaterial(
  materialId: string,
  userId: string
): Promise<{ flashcards: Flashcard[]; count: number }> {
  const url = `${API_URL}/api/flashcards/${encodeURIComponent(materialId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Download flashcards directly from database as .apkg file
 */
export async function downloadFlashcardsFromDb(
  materialId: string,
  userId: string
): Promise<{ blob: Blob; filename: string }> {
  const url = `${API_URL}/api/flashcards/${encodeURIComponent(materialId)}/download?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  // Extract filename from Content-Disposition header
  const contentDisposition = response.headers.get('Content-Disposition')
  let filename = `flashcards_${materialId}.apkg`
  
  if (contentDisposition) {
    // Parse filename from header: attachment; filename="Course - Lecture.apkg"
    const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
    if (match && match[1]) {
      filename = match[1]
    }
  }

  const blob = await response.blob()
  return { blob, filename }
}

/**
 * Cancel flashcard generation task
 */
export async function cancelFlashcardTask(
  taskId: string,
  userId: string
): Promise<{ success: boolean; message: string }> {
  const url = `${API_URL}/api/flashcards/cancel/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'POST',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Get active flashcard generation task for a course material
 * Returns null if no active task exists
 */
export async function getActiveFlashcardTask(
  materialId: string,
  userId: string
): Promise<FlashcardTaskStatus | null> {
  const url = `${API_URL}/api/flashcards/active/${encodeURIComponent(materialId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    // If 404, no active task exists (this is fine)
    if (response.status === 404) {
      return null
    }
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const data = await response.json()
  // If response is null, return null
  if (data === null) {
    return null
  }

  return data as FlashcardTaskStatus
}

/**
 * Retry syncing unsynced flashcards to AnkiWeb
 */
export async function retryAnkiWebSync(
  userId: string
): Promise<{ status: string; message: string; synced_count?: number; unsynced_count?: number }> {
  const url = `${API_URL}/api/flashcards/retry-ankiweb-sync?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'POST',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Export flashcards for a course material as CSV (legacy - now uses background tasks)
 * @deprecated Use generateFlashcards + getFlashcardTaskStatus + downloadFlashcards instead
 */
export async function exportFlashcards(
  materialId: string,
  userId: string
): Promise<{ blob: Blob; filename: string }> {
  // Start generation task
  const { task_id } = await generateFlashcards(materialId, userId)
  
  // Poll for completion
  const pollInterval = 2000 // 2 seconds
  const maxWaitTime = 600000 // 10 minutes
  const startTime = Date.now()
  
  while (Date.now() - startTime < maxWaitTime) {
    await new Promise(resolve => setTimeout(resolve, pollInterval))
    
    const status = await getFlashcardTaskStatus(task_id, userId)
    
    if (status.status === 'completed') {
      return downloadFlashcards(task_id, userId)
    }
    
    if (status.status === 'failed' || status.status === 'cancelled') {
      throw new Error(status.error_message || 'Flashcard generation failed')
    }
    
    // Continue polling if still running
  }
  
  throw new Error('Flashcard generation timed out')
}

/**
 * Submit quiz answers
 */
export async function submitQuiz(
  quizId: string,
  answers: Record<string, 'A' | 'B' | 'C' | 'D'>,
  userId: string
): Promise<QuizResult> {
  const response = await fetch(`${API_URL}/api/quiz/submit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      quiz_id: quizId,
      answers,
      user_id: userId,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// =============================================================================
// Knowledge Tracking API
// =============================================================================

/**
 * Knowledge level data for a single deck
 */
export interface DeckKnowledge {
  mastery_score: number
  total_cards: number
  new_cards: number
  learning_cards: number
  young_cards: number
  mature_cards: number
  avg_ease: number
  avg_interval_days: number
  retention_rate: number
  status: 'mastered' | 'progressing' | 'needs_review' | 'not_started' | 'no_cards'
  is_leaf: boolean
}

/**
 * Response from get_knowledge_levels endpoint
 */
export interface KnowledgeLevelsResponse {
  status: 'success' | 'error'
  overall_mastery: number
  total_cards: number
  decks: Record<string, DeckKnowledge>
  recommendations: string[]
  error?: string
}

/**
 * Knowledge level data for a single lecture
 */
export interface LectureKnowledge {
  material_id: string | null
  name: string
  deck_name: string
  mastery_score: number
  total_cards: number
  new_cards: number
  learning_cards: number
  young_cards: number
  mature_cards: number
  avg_ease: number
  avg_interval_days: number
  retention_rate: number
  status: string
}

/**
 * Response from get_course_knowledge_levels endpoint
 */
export interface CourseKnowledgeResponse {
  status: 'success' | 'error'
  course: {
    id: string
    title: string
    overall_mastery: number
    total_cards: number
  }
  lectures: LectureKnowledge[]
  weakest_lecture: string | null
  strongest_lecture: string | null
  recommendations: string[]
  error?: string
}

/**
 * Get knowledge levels for all Anki decks
 * 
 * Returns comprehensive mastery information for all decks:
 * - Mastery score (0.0-1.0) based on card states, ease factors, and retention
 * - Card distribution (new, learning, young, mature)
 * - Status labels (mastered, progressing, needs_review, not_started)
 * - Study recommendations
 */
export async function getKnowledgeLevels(
  userId: string
): Promise<KnowledgeLevelsResponse> {
  const url = `${API_URL}/api/knowledge/levels?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Get knowledge levels for all lectures within a specific course
 * 
 * Returns per-lecture mastery breakdown:
 * - Course-level overall mastery (weighted by card count)
 * - Per-lecture mastery scores and card distributions
 * - Identifies weakest and strongest lectures
 * - Targeted study recommendations
 */
export async function getCourseKnowledgeLevels(
  courseId: string,
  userId: string
): Promise<CourseKnowledgeResponse> {
  const url = `${API_URL}/api/knowledge/course/${encodeURIComponent(courseId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// =============================================================================
// Anki Study History API
// =============================================================================

/**
 * Comprehensive daily study statistics from Anki
 */
export interface StudyHistoryEntry {
  date: string                    // "yyyy-MM-dd" format
  cards_reviewed: number          // Total reviews on this day
  time_spent_seconds: number      // Total study time in seconds
  again_count: number             // "Again" button presses (forgotten)
  hard_count: number              // "Hard" button presses
  good_count: number              // "Good" button presses
  easy_count: number              // "Easy" button presses
  new_cards: number               // Cards learned for first time
  review_cards: number            // Regular reviews
  relearn_cards: number           // Cards being relearned (lapses)
  avg_time_per_card_ms: number    // Average time per review in milliseconds
}

/**
 * Response from the study history endpoint
 */
export interface StudyHistoryResponse {
  status: 'success' | 'error'
  source: 'anki' | 'cache'
  days_requested: number
  data: StudyHistoryEntry[]
  error?: string
}

/**
 * Get Anki study history for a user
 * 
 * Returns comprehensive daily study statistics including:
 * - Cards reviewed per day
 * - Time spent studying
 * - Button press breakdown (Again/Hard/Good/Easy)
 * - Card type breakdown (New/Review/Relearn)
 * 
 * @param userId - User ID
 * @param days - Number of days of history (default 90)
 * @param cacheOnly - If true, returns cached data immediately without fetching from Anki (fast)
 */
export async function getStudyHistory(
  userId: string,
  days: number = 90,
  cacheOnly: boolean = false
): Promise<StudyHistoryResponse> {
  const url = `${API_URL}/api/anki/study-history?user_id=${encodeURIComponent(userId)}&days=${days}&cache_only=${cacheOnly}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

