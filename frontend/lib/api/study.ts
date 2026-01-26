/**
 * API Client Functions for Study Session
 * 
 * Handles communication with the backend API for:
 * - Chat initiation and messaging
 * - Page analysis retrieval
 * - SSE streaming
 */

import type { ChatMessage, PageAnalysisData, ToolCall, QuizResult } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Parse SSE chunk to extract message data
 * Supports both delta events, regular message chunks, and tool call events
 */
export function parseSSEChunk(chunk: string): { 
  node?: string
  messages?: Array<{ role: string; content: string }>
  type?: string
  delta?: string
  content?: string
  role?: string
  error?: string
  tool_calls?: ToolCall[]
  tool_call_id?: string
  result?: string
  message_id?: string
} | null {
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
 * Initiate a chat session for a study page
 */
export async function initiateChat(
  materialId: string,
  pageNumber: number,
  userId: string,
  onChunk: (chunk: { node?: string; messages?: Array<{ role: string; content: string }>; error?: string; type?: string; tool_calls?: ToolCall[]; message_id?: string }) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
  isInitialOpen: boolean = false
): Promise<{ close: () => void }> {
  // #region agent log
  const requestUrl = `${API_URL}/api/chat/initiate`;
  fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:57',message:'initiateChat: Request start',data:{apiUrl:API_URL,requestUrl,method:'POST',materialId,pageNumber,userId,isInitialOpen},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:68',message:'initiateChat: Fetch error (network)',data:{error:fetchError instanceof Error ? fetchError.message : String(fetchError),errorType:fetchError instanceof Error ? fetchError.constructor.name : typeof fetchError,requestUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    throw fetchError;
  }

  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:71',message:'initiateChat: Response received',data:{status:response.status,statusText:response.statusText,ok:response.ok,headers:Object.fromEntries(response.headers.entries())},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion

  if (!response.ok) {
    // #region agent log
    const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:72',message:'initiateChat: Response error',data:{status:response.status,errorData},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    throw new Error(errorData.detail || `HTTP ${response.status}`)
  }

  // Create a simple EventSource-like interface using ReadableStream
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('No response body')
  }

  let buffer = ''
  let isClosed = false

  const processStream = async () => {
    try {
      console.log('[initiateChat] Starting stream processing...')
      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          console.log('[initiateChat] Stream done')
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
            console.log('[initiateChat] Received line:', line.substring(0, 100))
            if (line === 'data: [DONE]' || line.trim() === 'data: [DONE]') {
              console.log('[initiateChat] Stream complete')
              if (!isClosed) {
                isClosed = true
                onComplete?.()
              }
              return
            }
            const chunk = parseSSEChunk(line)
            if (chunk) {
              console.log('[initiateChat] Parsed chunk:', chunk)
              onChunk(chunk)
            }
          }
        }
      }
    } catch (error) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:124',message:'initiateChat: Stream error',data:{error:error instanceof Error ? error.message : String(error),errorType:error instanceof Error ? error.constructor.name : typeof error},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      console.error('[initiateChat] Stream error:', error)
      if (!isClosed) {
        isClosed = true
        onError?.(error instanceof Error ? error : new Error('Stream error'))
      }
    }
  }

  // Start processing stream (don't await, but handle errors)
  processStream().catch((error) => {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:134',message:'initiateChat: Unhandled stream error',data:{error:error instanceof Error ? error.message : String(error),errorType:error instanceof Error ? error.constructor.name : typeof error},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    console.error('[initiateChat] Unhandled stream error:', error)
    if (!isClosed) {
      isClosed = true
      onError?.(error instanceof Error ? error : new Error('Stream error'))
    }
  })

  // Return a close function for cleanup
  return {
    close: () => {
      console.log('[initiateChat] Closing stream')
      isClosed = true
      reader.cancel()
    },
  }
}

/**
 * Send a message in an existing chat session
 */
export function sendMessage(
  materialId: string,
  message: string,
  userId: string,
  onChunk: (chunk: { node?: string; messages?: Array<{ role: string; content: string }>; error?: string; type?: string; tool_calls?: ToolCall[]; message_id?: string }) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
  pageNumber?: number
): Promise<void> {
  return new Promise((resolve, reject) => {
    const body: Record<string, any> = {
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

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) {
          throw new Error('No response body')
        }

        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          
          if (done) {
            onComplete?.()
            resolve()
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.trim()) {
              const chunk = parseSSEChunk(line)
              if (chunk) {
                onChunk(chunk)
              }
            }
          }
        }
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
  // #region agent log
  const requestUrl = `${API_URL}/api/study/session?material_id=${encodeURIComponent(materialId)}&user_id=${encodeURIComponent(userId)}`;
  fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:255',message:'getStudySession: Request start',data:{apiUrl:API_URL,requestUrl,method:'GET',materialId,userId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
  // #endregion
  let response: Response;
  try {
    response = await fetch(requestUrl, {
      method: 'GET',
    })
  } catch (fetchError) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:260',message:'getStudySession: Fetch error (network)',data:{error:fetchError instanceof Error ? fetchError.message : String(fetchError),errorType:fetchError instanceof Error ? fetchError.constructor.name : typeof fetchError,requestUrl},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    throw fetchError;
  }

  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:260',message:'getStudySession: Response received',data:{status:response.status,statusText:response.statusText,ok:response.ok},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
  // #endregion

  if (!response.ok) {
    // #region agent log
    const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'study.ts:263',message:'getStudySession: Response error',data:{status:response.status,errorData},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
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
  created_at: number
  completed_at?: number
}

/**
 * Start flashcard generation as a background task
 */
export async function generateFlashcards(
  materialId: string,
  userId: string
): Promise<{ task_id: string; status: string; message: string }> {
  const url = `${API_URL}/api/flashcards/generate?course_material_id=${encodeURIComponent(materialId)}&user_id=${encodeURIComponent(userId)}`
  
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
 * Download generated flashcard CSV file
 */
export async function downloadFlashcards(
  taskId: string,
  userId: string
): Promise<Blob> {
  const url = `${API_URL}/api/flashcards/download/${encodeURIComponent(taskId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.blob()
}

/**
 * Get flashcards for a course material from database
 */
export async function getFlashcardsForMaterial(
  materialId: string,
  userId: string
): Promise<{ flashcards: any[]; count: number }> {
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
 * Download flashcards directly from database as CSV
 */
export async function downloadFlashcardsFromDb(
  materialId: string,
  userId: string
): Promise<Blob> {
  const url = `${API_URL}/api/flashcards/${encodeURIComponent(materialId)}/download?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'GET',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.blob()
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
 * Export flashcards for a course material as CSV (legacy - now uses background tasks)
 * @deprecated Use generateFlashcards + getFlashcardTaskStatus + downloadFlashcards instead
 */
export async function exportFlashcards(
  materialId: string,
  userId: string
): Promise<Blob> {
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
