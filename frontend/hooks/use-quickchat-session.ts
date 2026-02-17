import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { 
  sendQuickChatMessage,
  warmupQuickChat,
  getMaterialInfo,
  QuickChatEvent, 
  QuickChatSearchResult,
} from '@/lib/api/quickchat'
import type { ChatMessage } from '@/types'

/**
 * State for viewing a material inline (PDF viewer mode)
 */
export interface ViewingMaterial {
  courseId: string
  materialId: string
  materialName: string
  pdfUrl: string
  pageCount: number
  currentPage: number
}

/**
 * Pending navigation waiting for user confirmation
 */
export interface PendingNavigation {
  courseId: string
  courseTitle: string
  materialId: string
  materialName: string
  pageNumber: number
}

export interface QuickChatSessionState {
  mode: 'discovery' | 'viewing'
  threadId: string | null
  coursesCount: number
  materialsCount: number
  // Viewing mode context (inline PDF viewer)
  viewingMaterial: ViewingMaterial | null
  // Pending navigation awaiting confirmation
  pendingNavigation: PendingNavigation | null
}

export function useQuickChatSession(userId: string) {
  const router = useRouter()
  
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [searchResults, setSearchResults] = useState<QuickChatSearchResult[]>([])
  const [sessionState, setSessionState] = useState<QuickChatSessionState>({
    mode: 'discovery',
    threadId: null,
    coursesCount: 0,
    materialsCount: 0,
    viewingMaterial: null,
    pendingNavigation: null,
  })
  
  const streamControllerRef = useRef<(() => void) | null>(null)
  const messageIdCounter = useRef(0)
  const currentAssistantMessageRef = useRef<string | null>(null)

  // Generate unique message ID
  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1
    return `qc-msg-${Date.now()}-${messageIdCounter.current}`
  }, [])

  // Track if session has been initialized
  const isInitializedRef = useRef(false)

  // Initialize the quick chat session
  const initializeSession = useCallback(async () => {
    if (!userId) return
    
    // Prevent double initialization (React StrictMode, effect re-runs)
    if (isInitializedRef.current) return
    isInitializedRef.current = true
    
    setIsLoading(true)
    
    try {
      // Generate thread_id on frontend to start warmup immediately
      const generatedThreadId = `quickchat-${userId}-${crypto.randomUUID()}`
      
      // Start warmup IMMEDIATELY (don't wait for initiate response)
      warmupQuickChat(userId, generatedThreadId).catch(err => 
        console.warn('Agent warmup failed:', err)
      )
      
      // Set thread_id and show greeting instantly (no network wait for greeting)
      const greeting = "Hallo! Ich bin dein Lernassistent. Frag mich einfach nach einem Thema, und ich zeige dir, wo es in deinen Vorlesungen behandelt wird!"
      
      // Add greeting message immediately
      const msgId = generateMessageId()
      setMessages([{
        id: msgId,
        role: 'assistant',
        content: greeting,
        timestamp: new Date().toISOString(),
      }])
      
      // Set session state with generated thread_id
      setSessionState(prev => ({
        ...prev,
        threadId: generatedThreadId,
        mode: 'discovery',
      }))
      
    } catch (error) {
      console.error('Failed to initialize quick chat:', error)
    } finally {
      setIsLoading(false)
    }
  }, [userId, generateMessageId])

  // Send a message
  const sendMessage = useCallback(async (message: string) => {
    if (!userId || !message.trim()) return
    
    // Add user message
    const userMsgId = generateMessageId()
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }])
    
    setIsStreaming(true)
    setSearchResults([]) // Clear previous search results
    
    // Create placeholder for assistant response
    const assistantMsgId = generateMessageId()
    currentAssistantMessageRef.current = assistantMsgId
    setMessages(prev => [...prev, {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    }])
    
    try {
      // Build context from viewing material if in viewing mode
      const context = sessionState.viewingMaterial ? {
        materialId: sessionState.viewingMaterial.materialId,
        pageNumber: sessionState.viewingMaterial.currentPage,
        courseId: sessionState.viewingMaterial.courseId,
      } : null
      
      const cleanup = await sendQuickChatMessage(
        userId,
        message,
        sessionState.threadId,
        context,
        (event: QuickChatEvent) => {
          switch (event.type) {
            case 'delta':
              // Append delta to assistant message
              setMessages(prev => {
                const idx = prev.findIndex(m => m.id === assistantMsgId)
                if (idx < 0) return prev
                const updated = [...prev]
                updated[idx] = {
                  ...updated[idx],
                  content: event.content || updated[idx].content + (event.delta || ''),
                }
                return updated
              })
              break
              
            case 'message':
              if (event.role === 'assistant' && event.content) {
                setMessages(prev => {
                  const idx = prev.findIndex(m => m.id === assistantMsgId)
                  if (idx < 0) return prev
                  const updated = [...prev]
                  updated[idx] = {
                    ...updated[idx],
                    content: event.content || '',
                  }
                  return updated
                })
              }
              break
              
            case 'tool_call':
              // Could show tool call indicator
              console.log('Tool call:', event.tool)
              break
              
            case 'search_results':
              if (event.results) {
                setSearchResults(event.results)
              }
              break
              
            case 'open_material':
              // Auto-open the PDF viewer at the best result
              if (event.material_id && event.page_number) {
                // Fetch material info and open viewer
                getMaterialInfo(event.material_id)
                  .then(materialInfo => {
                    setSessionState(prev => ({
                      ...prev,
                      mode: 'viewing',
                      viewingMaterial: {
                        courseId: event.course_id || '',
                        materialId: event.material_id || '',
                        materialName: event.material_name || '',
                        pdfUrl: materialInfo.pdf_url,
                        pageCount: materialInfo.page_count,
                        currentPage: event.page_number || 1,
                      },
                      // Clear pending navigation after confirmed
                      pendingNavigation: null,
                    }))
                    // Clear search results when entering viewing mode
                    setSearchResults([])
                  })
                  .catch(err => console.error('Failed to auto-open material:', err))
              }
              break
            
            case 'pending_navigation':
              // Store pending navigation for user confirmation
              // The agent has asked the user if they want to navigate
              // When user confirms, backend will send open_material
              if (event.material_id && event.page_number) {
                setSessionState(prev => ({
                  ...prev,
                  pendingNavigation: {
                    courseId: event.course_id || '',
                    courseTitle: event.course_title || '',
                    materialId: event.material_id || '',
                    materialName: event.material_name || '',
                    pageNumber: event.page_number || 1,
                  },
                }))
              }
              break
              
            case 'navigate':
              // Navigate to study page (legacy - external navigation)
              if (event.course_id && event.material_id && event.page_number) {
                router.push(
                  `/dashboard/courses/${event.course_id}/study/${event.material_id}?page=${event.page_number}`
                )
              }
              break
              
            case 'error':
              console.error('Quick chat error:', event.error)
              setMessages(prev => {
                const idx = prev.findIndex(m => m.id === assistantMsgId)
                if (idx < 0) return prev
                const updated = [...prev]
                updated[idx] = {
                  ...updated[idx],
                  content: `Fehler: ${event.error}`,
                }
                return updated
              })
              break
          }
        }
      )
      
      streamControllerRef.current = cleanup
    } catch (error) {
      console.error('Failed to send message:', error)
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === assistantMsgId)
        if (idx < 0) return prev
        const updated = [...prev]
        updated[idx] = {
          ...updated[idx],
          content: `Fehler: ${error instanceof Error ? error.message : 'Unbekannter Fehler'}`,
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
      currentAssistantMessageRef.current = null
    }
  }, [userId, sessionState, generateMessageId, router])

  // Navigate to a search result (external navigation - legacy)
  const navigateToResult = useCallback((result: QuickChatSearchResult) => {
    router.push(
      `/dashboard/courses/${result.course_id}/study/${result.material_id}?page=${result.page_number}`
    )
  }, [router])

  // Open material inline (enter viewing mode with PDF viewer)
  const openMaterial = useCallback(async (result: QuickChatSearchResult) => {
    try {
      // Fetch material info (PDF URL, page count)
      const materialInfo = await getMaterialInfo(result.material_id)
      
      setSessionState(prev => ({
        ...prev,
        mode: 'viewing',
        viewingMaterial: {
          courseId: result.course_id,
          materialId: result.material_id,
          materialName: result.material_name,
          pdfUrl: materialInfo.pdf_url,
          pageCount: materialInfo.page_count,
          currentPage: result.page_number,
        },
      }))
      
      // Clear search results when entering viewing mode
      setSearchResults([])
    } catch (error) {
      console.error('Failed to open material:', error)
    }
  }, [])

  // Close material viewer (return to discovery mode)
  const closeMaterial = useCallback(() => {
    setSessionState(prev => ({
      ...prev,
      mode: 'discovery',
      viewingMaterial: null,
    }))
  }, [])

  // Update current page in viewing mode (NO auto-response)
  const setCurrentPage = useCallback((page: number) => {
    setSessionState(prev => {
      if (!prev.viewingMaterial) return prev
      return {
        ...prev,
        viewingMaterial: {
          ...prev.viewingMaterial,
          currentPage: page,
        },
      }
    })
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamControllerRef.current) {
        streamControllerRef.current()
      }
    }
  }, [])

  // Initialize session on mount
  useEffect(() => {
    if (userId) {
      initializeSession()
    }
  }, [userId, initializeSession])

  return {
    messages,
    isLoading,
    isStreaming,
    searchResults,
    sessionState,
    sendMessage,
    navigateToResult,
    openMaterial,
    closeMaterial,
    setCurrentPage,
    initializeSession,
  }
}
