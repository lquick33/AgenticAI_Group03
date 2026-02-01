/**
 * API Client Functions for Quick Chat
 * 
 * Handles communication with the backend API for:
 * - Quick chat session initiation
 * - Sending messages in quick chat
 * - Direct topic search
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Search result from quick chat topic search
 */
export interface QuickChatSearchResult {
  course_id: string
  course_title: string
  course_color: string | null
  material_id: string
  material_name: string
  page_number: number
  summary: string
  key_terms: string[]
  rank: number
}

/**
 * Response from quick chat topic search
 */
export interface QuickChatSearchResponse {
  found: boolean
  message: string
  results: QuickChatSearchResult[]
}

/**
 * SSE event types from quick chat
 */
export type QuickChatEventType = 
  | 'message' 
  | 'delta' 
  | 'tool_call' 
  | 'search_results' 
  | 'session' 
  | 'stats'
  | 'navigate' 
  | 'open_material'
  | 'pending_navigation'
  | 'error'

/**
 * SSE event from quick chat stream
 */
export interface QuickChatEvent {
  type: QuickChatEventType
  // Message events
  role?: 'assistant' | 'user'
  content?: string
  delta?: string
  // Tool call events
  tool?: string
  // Search results events
  results?: QuickChatSearchResult[]
  // Session events
  thread_id?: string
  mode?: 'discovery' | 'tutoring'
  courses_count?: number
  materials_count?: number
  // Navigate/open_material events
  course_id?: string
  course_title?: string
  material_id?: string
  material_name?: string
  page_number?: number
  // Error events
  error?: string
}

/**
 * Response from quick chat initiate
 */
export interface QuickChatInitiateResponse {
  greeting: string
  thread_id: string
  mode: 'discovery' | 'tutoring'
}

/**
 * Initiate a quick chat session
 * 
 * Returns instantly with greeting and thread_id (no SSE streaming).
 * 
 * @param userId User ID
 * @returns Initiate response with greeting and thread_id
 */
export async function initiateQuickChat(
  userId: string
): Promise<QuickChatInitiateResponse> {
  const url = `${API_URL}/api/quickchat/initiate`
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_id: userId }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Pre-warm the quick chat agent for faster first response.
 * Call this after receiving thread_id from initiate, while user is typing.
 * 
 * @param userId User ID
 * @param threadId Thread ID from initiate response
 * @returns Warmup status
 */
export async function warmupQuickChat(
  userId: string,
  threadId: string
): Promise<{ status: string; thread_id?: string; error?: string }> {
  const url = `${API_URL}/api/quickchat/warmup`
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ user_id: userId, thread_id: threadId }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Send a message in quick chat
 * 
 * @param userId User ID
 * @param message User message
 * @param threadId Thread ID from initiate (for pre-warmed agent)
 * @param context Optional tutoring context
 * @param onEvent Callback for SSE events
 * @returns Cleanup function
 */
export async function sendQuickChatMessage(
  userId: string,
  message: string,
  threadId: string | null,
  context: {
    materialId?: string
    pageNumber?: number
    courseId?: string
  } | null,
  onEvent: (event: QuickChatEvent) => void
): Promise<() => void> {
  const url = `${API_URL}/api/quickchat/message`
  
  const body: Record<string, unknown> = {
    user_id: userId,
    message,
  }
  
  if (threadId) {
    body.thread_id = threadId
  }
  
  if (context?.materialId) {
    body.material_id = context.materialId
    body.page_number = context.pageNumber
    body.course_id = context.courseId
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let isAborted = false

  const processStream = async () => {
    if (!reader) return

    try {
      while (!isAborted) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (data === '[DONE]') {
              return
            }
            try {
              const event = JSON.parse(data) as QuickChatEvent
              onEvent(event)
            } catch (e) {
              console.warn('Failed to parse SSE event:', data)
            }
          }
        }
      }
    } catch (error) {
      if (!isAborted) {
        console.error('Error reading stream:', error)
        onEvent({ type: 'error', error: String(error) })
      }
    }
  }

  processStream()

  return () => {
    isAborted = true
    reader?.cancel()
  }
}

/**
 * Response from getMaterialInfo
 */
export interface MaterialInfoResponse {
  material_id: string
  file_name: string
  pdf_url: string
  page_count: number
}

/**
 * Get material info (PDF URL, page count) for inline viewing
 * 
 * @param materialId Material ID
 * @returns Material info including PDF URL
 */
export async function getMaterialInfo(
  materialId: string
): Promise<MaterialInfoResponse> {
  const url = `${API_URL}/api/quickchat/material/${materialId}`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Direct topic search without going through the agent
 * 
 * @param userId User ID
 * @param query Search query
 * @param language Language for search ('de', 'en', or 'auto')
 * @param limit Maximum number of results
 * @returns Search response
 */
export async function searchQuickChatTopics(
  userId: string,
  query: string,
  language: string = 'auto',
  limit: number = 10
): Promise<QuickChatSearchResponse> {
  const params = new URLSearchParams({
    user_id: userId,
    query,
    language,
    limit: String(limit),
  })
  
  const url = `${API_URL}/api/quickchat/search?${params}`
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}
