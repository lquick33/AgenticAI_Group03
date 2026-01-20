"use client"

import { useState, useEffect, useRef, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { Panel, Group, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInterface } from './chat-interface'
import { initiateChat, sendMessage, getStudySession } from '@/lib/api/study'
import type { ChatMessage, ToolCall } from '@/types'

// Dynamically import PDF Viewer with SSR disabled
const PdfViewer = dynamic(() => import('./pdf-viewer').then((mod) => ({ default: mod.PdfViewer })), {
  ssr: false,
})

interface StudyReaderProps {
  materialId: string
  courseId: string
  pdfUrl: string
  pageCount: number
  userId: string
}

export function StudyReader({
  materialId,
  courseId,
  pdfUrl,
  pageCount,
  userId,
}: StudyReaderProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [showTools, setShowTools] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('study-reader-show-tools')
      return saved === 'true'
    }
    return false
  })
  const [toolCallsByMessage, setToolCallsByMessage] = useState<Map<string, ToolCall[]>>(new Map())
  const streamControllerRef = useRef<{ close: () => void } | null>(null)
  const messageIdCounter = useRef(0)
  const chatPanelRef = useRef<HTMLDivElement | null>(null)
  
  // Debouncing and request tracking for page changes
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)
  const currentRequestIdRef = useRef<string | null>(null)
  const pageChangeHistoryRef = useRef<Array<{ page: number; timestamp: number }>>([])
  
  // Typewriter animation state
  const typewriterRef = useRef<{
    intervalId: NodeJS.Timeout | null
    fullText: string
    currentIndex: number
    messageId: string | null
  }>({
    intervalId: null,
    fullText: '',
    currentIndex: 0,
    messageId: null,
  })

  // Generate unique message ID
  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1
    return `msg-${Date.now()}-${messageIdCounter.current}`
  }, [])

  // Stop any running typewriter animation
  const stopTypewriter = useCallback(() => {
    if (typewriterRef.current.intervalId) {
      clearInterval(typewriterRef.current.intervalId)
      typewriterRef.current.intervalId = null
    }
    typewriterRef.current.fullText = ''
    typewriterRef.current.currentIndex = 0
    typewriterRef.current.messageId = null
  }, [])

  // Start typewriter animation for assistant message
  const startTypewriter = useCallback((fullText: string, messageId: string, speed: number = 40) => {
    // If typewriter is already running for this message, just update the fullText
    if (typewriterRef.current.messageId === messageId && typewriterRef.current.intervalId) {
      // Extend the fullText if new content is longer
      if (fullText.length > typewriterRef.current.fullText.length) {
        typewriterRef.current.fullText = fullText
        console.log('[StudyReader] Extended typewriter text, new length:', fullText.length)
      }
      return
    }

    // Stop any existing typewriter
    stopTypewriter()

    // Initialize typewriter state
    typewriterRef.current.fullText = fullText
    typewriterRef.current.currentIndex = 0
    typewriterRef.current.messageId = messageId

    console.log('[StudyReader] Starting typewriter animation, text length:', fullText.length, 'speed:', speed, 'ms per char')

    // Start animation
    typewriterRef.current.intervalId = setInterval(() => {
      const { fullText, currentIndex, messageId: msgId } = typewriterRef.current

      if (currentIndex >= fullText.length) {
        // Animation complete
        console.log('[StudyReader] Typewriter animation complete')
        stopTypewriter()
        return
      }

      // Increment index (show 1 character at a time for smoother, more visible effect)
      const charsPerStep = 1
      typewriterRef.current.currentIndex += charsPerStep

      // Update message content
      setMessages((prev) => {
        const index = prev.findIndex((m) => m.id === msgId)
        if (index >= 0) {
          const updated = [...prev]
          updated[index] = {
            ...updated[index],
            content: fullText.slice(0, typewriterRef.current.currentIndex),
          }
          return updated
        }
        return prev
      })
    }, speed)
  }, [stopTypewriter])

  // Internal function to initiate chat with request ID tracking
  const initiateChatForPage = useCallback(
    async (page: number, requestId: string, isInitialOpen: boolean = false) => {
      // Stop any running typewriter
      stopTypewriter()

      // Close existing stream
      if (streamControllerRef.current) {
        streamControllerRef.current.close()
        streamControllerRef.current = null
      }

      // Add placeholder assistant message for typing indicator when page changes
      // Only add if we don't already have a streaming message
      setMessages((prev) => {
        const hasStreamingMessage = prev.some(
          (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
        )
        if (!hasStreamingMessage) {
          return [
            ...prev,
            {
              id: `streaming-${generateMessageId()}`,
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
            },
          ]
        }
        return prev
      })

      setIsLoading(true)
      setIsStreaming(true)

      try {
        console.log('[StudyReader] Initiating chat for page', page, 'requestId:', requestId, 'isInitialOpen:', isInitialOpen)
        const streamController = await initiateChat(
        materialId,
        page,
        userId,
        (chunk) => {
          // Check if this chunk belongs to the current request
          // If requestId doesn't match, ignore this chunk (it's from an outdated request)
          if (currentRequestIdRef.current !== requestId) {
            console.log('[StudyReader] Ignoring chunk from outdated request:', requestId, 'current:', currentRequestIdRef.current)
            return
          }

          console.log('[StudyReader] Received chunk for request:', requestId, chunk)
          if (chunk.error) {
            console.error('[StudyReader] Chat error:', chunk.error)
            setIsLoading(false)
            setIsStreaming(false)
            
            // Show error message in chat
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                // Replace streaming message with error
                const updated = [...prev]
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  id: generateMessageId(), // Finalize ID
                  content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                }
                return updated
              } else {
                // Add error message if no streaming message exists
                return [
                  ...prev,
                  {
                    id: generateMessageId(),
                    role: 'assistant',
                    content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                    timestamp: new Date().toISOString(),
                  },
                ]
              }
            })
            return
          }

          // Handle tool call events
          if (chunk.type === 'tool_call' && chunk.tool_calls) {
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                const messageId = prev[lastStreamingIndex].id
                setToolCallsByMessage((prevMap) => {
                  const newMap = new Map(prevMap)
                  const existing = newMap.get(messageId) || []
                  newMap.set(messageId, [...existing, ...chunk.tool_calls])
                  return newMap
                })
                
                // Also update the message with tool calls
                const updated = [...prev]
                const currentToolCalls = toolCallsByMessage.get(messageId) || []
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  toolCalls: [...currentToolCalls, ...chunk.tool_calls],
                }
                return updated
              }
              return prev
            })
            return
          }

          // Handle tool response events
          if (chunk.type === 'tool_response' && chunk.tool_call_id && chunk.result) {
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                const messageId = prev[lastStreamingIndex].id
                const updated = [...prev]
                
                // Find the tool call with matching ID and update it with result
                if (updated[lastStreamingIndex].toolCalls) {
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    toolCalls: updated[lastStreamingIndex].toolCalls!.map(toolCall => 
                      toolCall.id === chunk.tool_call_id
                        ? { ...toolCall, result: chunk.result, state: 'completed' as const }
                        : toolCall
                    ),
                  }
                }
                
                return updated
              }
              return prev
            })
            return
          }

          // Handle delta events for ghostwriter effect
          if (chunk.type === 'delta' && chunk.role === 'assistant' && chunk.delta) {
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )

              if (lastStreamingIndex >= 0) {
                // Append delta to existing streaming message
                const updated = [...prev]
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  content: (updated[lastStreamingIndex].content || '') + chunk.delta,
                }
                return updated
              } else {
                // Create new streaming message if none exists
                return [
                  ...prev,
                  {
                    id: `streaming-${generateMessageId()}`,
                    role: 'assistant',
                    content: chunk.delta,
                    timestamp: new Date().toISOString(),
                  },
                ]
              }
            })
            return
          }

          // Handle regular message chunks (for compatibility and tool responses)
          let messages: Array<{ role: string; content: any }> = []
          
          if (chunk.messages) {
            // Direct messages array
            messages = chunk.messages
          } else {
            // Look for messages in nested structure (e.g., chunk.agent.messages)
            for (const key in chunk) {
              // Ignore tool-node messages in the UI – they contain internal JSON summaries
              if (key === 'tools') {
                continue
              }

              if (chunk[key] && chunk[key].messages && Array.isArray(chunk[key].messages)) {
                messages = chunk[key].messages
                break
              }
            }
          }

          if (messages.length > 0) {
            messages.forEach((msg) => {
              // Handle content as string or array (LangChain format)
              let contentText = ''
              if (typeof msg.content === 'string') {
                contentText = msg.content
              } else if (Array.isArray(msg.content)) {
                // Extract text from array format: [{"type": "text", "text": "..."}]
                contentText = msg.content
                  .map((item: any) => {
                    if (typeof item === 'string') {
                      return item
                    } else if (item && typeof item === 'object') {
                      return item.text || item.content || ''
                    }
                    return ''
                  })
                  .filter((text: string) => text)
                  .join('')
              } else if (msg.content && typeof msg.content === 'object') {
                // Handle object format
                contentText = msg.content.text || msg.content.content || JSON.stringify(msg.content)
              }

              console.log('[StudyReader] Processing message:', msg.role, contentText?.substring(0, 50), 'Full length:', contentText?.length)
              if (msg.role === 'assistant' && contentText) {
                // Find or create streaming message
                setMessages((prev) => {
                  const lastStreamingIndex = prev.findLastIndex(
                    (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                  )

                  let streamingMessageId: string

                  if (lastStreamingIndex >= 0) {
                    streamingMessageId = prev[lastStreamingIndex].id
                    const existingMessage = prev[lastStreamingIndex]
                    
                    // Always update/start typewriter with the latest text
                    // This ensures we start animating immediately, even if text is incomplete
                    console.log('[StudyReader] Updating/starting typewriter, length:', contentText.length)
                    startTypewriter(contentText, streamingMessageId, 40)
                    
                    return prev
                  } else {
                    // Create new streaming message
                    console.log('[StudyReader] Adding new assistant message for page', page, 'length:', contentText.length)
                    const newId = `streaming-${generateMessageId()}`
                    streamingMessageId = newId
                    const updated = [
                      ...prev,
                      {
                        id: newId,
                        role: 'assistant' as const,
                        content: '',
                        timestamp: new Date().toISOString(),
                      },
                    ]
                    // Start typewriter immediately with whatever text we have
                    startTypewriter(contentText, newId, 40)
                    return updated
                  }
                })
              }
            })
          }
        },
        (error) => {
          // Only handle error if this is still the current request
          if (currentRequestIdRef.current !== requestId) {
            console.log('[StudyReader] Ignoring error from outdated request:', requestId)
            return
          }
          
          console.error('[StudyReader] Chat initiation error:', error)
          setIsLoading(false)
          setIsStreaming(false)
          
          // Show error message in chat
          setMessages((prev) => {
            const lastStreamingIndex = prev.findLastIndex(
              (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
            )
            
            if (lastStreamingIndex >= 0) {
              // Replace streaming message with error
              const updated = [...prev]
              updated[lastStreamingIndex] = {
                ...updated[lastStreamingIndex],
                id: generateMessageId(), // Finalize ID
                content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
              }
              return updated
            } else {
              // Add error message if no streaming message exists
              return [
                ...prev,
                {
                  id: generateMessageId(),
                  role: 'assistant',
                  content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                  timestamp: new Date().toISOString(),
                },
              ]
            }
          })
        },
        () => {
          // Only handle completion if this is still the current request
          if (currentRequestIdRef.current !== requestId) {
            console.log('[StudyReader] Ignoring completion from outdated request:', requestId)
            return
          }
          
          console.log('[StudyReader] Chat stream completed for request:', requestId)
          setIsLoading(false)
          setIsStreaming(false)
          
          // Get full text before finalizing
          const fullText = typewriterRef.current.fullText
          
          setMessages((prev) => {
            return prev.map((msg) => {
              if (msg.id.startsWith('streaming-')) {
                // If typewriter is running for this message, update its messageId to the new ID
                const newId = generateMessageId()
                if (typewriterRef.current.messageId === msg.id) {
                  // Update typewriter to use new ID so it can continue updating
                  typewriterRef.current.messageId = newId
                  console.log('[StudyReader] Updated typewriter messageId to:', newId)
                }
                
                // Set full content immediately so user sees it, even if typewriter is still running
                const finalContent = fullText || typewriterRef.current.fullText || msg.content || ''
                
                console.log('[StudyReader] Finalizing message:', {
                  oldId: msg.id,
                  newId,
                  typewriterRunning: !!typewriterRef.current.intervalId,
                  fullTextLength: fullText?.length || 0,
                  finalContentLength: finalContent.length
                })
                
                return {
                  ...msg,
                  id: newId,
                  content: finalContent, // Set full content immediately
                }
              }
              return msg
            })
          })
          
          if (streamControllerRef.current) {
            streamControllerRef.current.close()
            streamControllerRef.current = null
          }
        },
        isInitialOpen
      )

        streamControllerRef.current = streamController
      } catch (error) {
        // Only handle error if this is still the current request
        if (currentRequestIdRef.current !== requestId) {
          console.log('[StudyReader] Ignoring error from outdated request:', requestId)
          return
        }
        
        console.error('Error initiating chat:', error)
        setIsLoading(false)
        setIsStreaming(false)
        
        // Show error message in chat
        setMessages((prev) => {
          const lastStreamingIndex = prev.findLastIndex(
            (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
          )
          
          if (lastStreamingIndex >= 0) {
            // Replace streaming message with error
            const updated = [...prev]
            updated[lastStreamingIndex] = {
              ...updated[lastStreamingIndex],
              id: generateMessageId(), // Finalize ID
              content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
            }
            return updated
          } else {
            // Add error message if no streaming message exists
            return [
              ...prev,
              {
                id: generateMessageId(),
                role: 'assistant',
                content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                timestamp: new Date().toISOString(),
              },
            ]
          }
        })
      }
    },
    [materialId, userId, generateMessageId, startTypewriter, stopTypewriter]
  )

  // Handle page change with debouncing and fast scrolling detection
  const handlePageChange = useCallback(
    async (newPage: number, skipStateUpdate: boolean = false, isInitialOpen: boolean = false) => {
      if (newPage < 1 || newPage > pageCount) return

      // Only update state if not explicitly skipped (to prevent double triggers during init)
      if (!skipStateUpdate) {
        setCurrentPage(newPage)
      }

      // Track page change history for fast scrolling detection
      const now = Date.now()
      pageChangeHistoryRef.current.push({ page: newPage, timestamp: now })
      
      // Keep only last 5 page changes (within last 2 seconds)
      pageChangeHistoryRef.current = pageChangeHistoryRef.current
        .filter((entry) => now - entry.timestamp < 2000)
        .slice(-5)

      // Check if user is scrolling fast (more than 3 pages in 1 second)
      const recentChanges = pageChangeHistoryRef.current.filter(
        (entry) => now - entry.timestamp < 1000
      )
      const isFastScrolling = recentChanges.length > 3

      if (isFastScrolling && !isInitialOpen) {
        console.log('[StudyReader] Fast scrolling detected, skipping chat initiation for page', newPage)
        // Just update the page, don't initiate chat
        // Remove any existing streaming messages
        setMessages((prev) => {
          return prev.filter((msg) => !msg.id.startsWith('streaming-'))
        })
        setIsLoading(false)
        setIsStreaming(false)
        return
      }

      // Clear existing debounce timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
        debounceTimerRef.current = null
      }

      // Generate new request ID
      const requestId = `req-${Date.now()}-${newPage}-${Math.random().toString(36).substr(2, 9)}`
      currentRequestIdRef.current = requestId

      // Set up debounced chat initiation
      debounceTimerRef.current = setTimeout(async () => {
        // Check if this is still the latest request
        if (currentRequestIdRef.current !== requestId) {
          console.log('[StudyReader] Request outdated, skipping:', requestId)
          return
        }

        console.log('[StudyReader] Debounce completed, initiating chat for page', newPage, 'requestId:', requestId)
        await initiateChatForPage(newPage, requestId, isInitialOpen)
      }, 500) // 500ms debounce delay
    },
    [pageCount, initiateChatForPage]
  )

  // Handle user message
  const handleSendMessage = useCallback(
    async (message: string) => {
      // Add user message immediately
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      }
      
      // Add placeholder assistant message for typing indicator
      const placeholderAssistant: ChatMessage = {
        id: `streaming-${generateMessageId()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }
      
      setMessages((prev) => [...prev, userMessage, placeholderAssistant])

      setIsLoading(true)
      setIsStreaming(true)

      // Stop any running typewriter
      stopTypewriter()

      try {
        await sendMessage(
          materialId,
          message,
          userId,
          (chunk) => {
            if (chunk.error) {
              console.error('Chat error:', chunk.error)
              setIsLoading(false)
              setIsStreaming(false)
              
              // Show error message in chat
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  // Replace streaming message with error
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    id: generateMessageId(), // Finalize ID
                    content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                  }
                  return updated
                } else {
                  // Add error message if no streaming message exists
                  return [
                    ...prev,
                    {
                      id: generateMessageId(),
                      role: 'assistant',
                      content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                      timestamp: new Date().toISOString(),
                    },
                  ]
                }
              })
              return
            }

            // Handle tool call events
            if (chunk.type === 'tool_call' && chunk.tool_calls) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const messageId = prev[lastStreamingIndex].id
                  setToolCallsByMessage((prevMap) => {
                    const newMap = new Map(prevMap)
                    const existing = newMap.get(messageId) || []
                    newMap.set(messageId, [...existing, ...chunk.tool_calls])
                    return newMap
                  })
                  
                  const updated = [...prev]
                  const currentToolCalls = toolCallsByMessage.get(messageId) || []
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    toolCalls: [...currentToolCalls, ...chunk.tool_calls],
                  }
                  return updated
                }
                return prev
              })
              return
            }

            // Handle tool response events
            if (chunk.type === 'tool_response' && chunk.tool_call_id && chunk.result) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const updated = [...prev]
                  
                  // Find the tool call with matching ID and update it with result
                  if (updated[lastStreamingIndex].toolCalls) {
                    updated[lastStreamingIndex] = {
                      ...updated[lastStreamingIndex],
                      toolCalls: updated[lastStreamingIndex].toolCalls!.map(toolCall => 
                        toolCall.id === chunk.tool_call_id
                          ? { ...toolCall, result: chunk.result, state: 'completed' as const }
                          : toolCall
                      ),
                    }
                  }
                  
                  return updated
                }
                return prev
              })
              return
            }

            // Handle delta events for ghostwriter effect
            if (chunk.type === 'delta' && chunk.role === 'assistant' && chunk.delta) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )

                if (lastStreamingIndex >= 0) {
                  // Append delta to existing streaming message
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    content: (updated[lastStreamingIndex].content || '') + chunk.delta,
                  }
                  return updated
                } else {
                  // Create new streaming message if none exists
                  return [
                    ...prev,
                    {
                      id: `streaming-${generateMessageId()}`,
                      role: 'assistant',
                      content: chunk.delta,
                      timestamp: new Date().toISOString(),
                    },
                  ]
                }
              })
              return
            }

            // Handle delta events for ghostwriter effect
            if (chunk.type === 'delta' && chunk.role === 'assistant' && chunk.delta) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )

                if (lastStreamingIndex >= 0) {
                  // Append delta to existing streaming message
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    content: (updated[lastStreamingIndex].content || '') + chunk.delta,
                  }
                  return updated
                } else {
                  // Create new streaming message if none exists
                  return [
                    ...prev,
                    {
                      id: `streaming-${generateMessageId()}`,
                      role: 'assistant',
                      content: chunk.delta,
                      timestamp: new Date().toISOString(),
                    },
                  ]
                }
              })
              return
            }

            // Handle regular message chunks (for compatibility and tool responses)
            let messages: Array<{ role: string; content: any }> = []
            
            if (chunk.messages) {
              // Direct messages array
              messages = chunk.messages
            } else {
              // Look for messages in nested structure (e.g., chunk.agent.messages)
              for (const key in chunk) {
                if (chunk[key] && chunk[key].messages && Array.isArray(chunk[key].messages)) {
                  messages = chunk[key].messages
                  break
                }
              }
            }

            if (messages.length > 0) {
              messages.forEach((msg) => {
                // Handle content as string or array (LangChain format)
                let contentText = ''
                if (typeof msg.content === 'string') {
                  contentText = msg.content
                } else if (Array.isArray(msg.content)) {
                  // Extract text from array format: [{"type": "text", "text": "..."}]
                  contentText = msg.content
                    .map((item: any) => {
                      if (typeof item === 'string') {
                        return item
                      } else if (item && typeof item === 'object') {
                        return item.text || item.content || ''
                      }
                      return ''
                    })
                    .filter((text: string) => text)
                    .join('')
                } else if (msg.content && typeof msg.content === 'object') {
                  // Handle object format
                  contentText = msg.content.text || msg.content.content || JSON.stringify(msg.content)
                }

                console.log('[StudyReader] Processing message (sendMessage):', msg.role, contentText?.substring(0, 50), 'Full length:', contentText?.length)
                if (msg.role === 'assistant' && contentText) {
                  // Find or create streaming message
                  setMessages((prev) => {
                    const lastStreamingIndex = prev.findLastIndex(
                      (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                    )

                    let streamingMessageId: string

                    if (lastStreamingIndex >= 0) {
                      streamingMessageId = prev[lastStreamingIndex].id
                      const existingMessage = prev[lastStreamingIndex]
                      
                      // Always update/start typewriter with the latest text
                      // This ensures we start animating immediately, even if text is incomplete
                      console.log('[StudyReader] Updating/starting typewriter (sendMessage), length:', contentText.length)
                      startTypewriter(contentText, streamingMessageId, 40)
                      
                      return prev
                    } else {
                      // Create new streaming message
                      console.log('[StudyReader] Adding new assistant message (sendMessage), length:', contentText.length)
                      const newId = `streaming-${generateMessageId()}`
                      streamingMessageId = newId
                      const updated = [
                        ...prev,
                        {
                          id: newId,
                          role: 'assistant' as const,
                          content: '',
                          timestamp: new Date().toISOString(),
                        },
                      ]
                      // Start typewriter immediately with whatever text we have
                      startTypewriter(contentText, newId, 40)
                      return updated
                    }
                  })
                }
              })
            }
          },
          (error) => {
            console.error('Send message error:', error)
            setIsLoading(false)
            setIsStreaming(false)
            
            // Show error message in chat
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                // Replace streaming message with error
                const updated = [...prev]
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  id: generateMessageId(), // Finalize ID
                  content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                }
                return updated
              } else {
                // Add error message if no streaming message exists
                return [
                  ...prev,
                  {
                    id: generateMessageId(),
                    role: 'assistant',
                    content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                    timestamp: new Date().toISOString(),
                  },
                ]
              }
            })
          },
          () => {
            console.log('[StudyReader] Send message stream completed')
            setIsLoading(false)
            setIsStreaming(false)
            
            // Get full text before finalizing
            const fullText = typewriterRef.current.fullText
            
            setMessages((prev) => {
              return prev.map((msg) => {
                if (msg.id.startsWith('streaming-')) {
                  // If typewriter is running for this message, update its messageId to the new ID
                  const newId = generateMessageId()
                  if (typewriterRef.current.messageId === msg.id) {
                    // Update typewriter to use new ID so it can continue updating
                    typewriterRef.current.messageId = newId
                    console.log('[StudyReader] Updated typewriter messageId to (sendMessage):', newId)
                  }
                  
                  // Set full content immediately so user sees it, even if typewriter is still running
                  const finalContent = fullText || typewriterRef.current.fullText || msg.content || ''
                  
                  console.log('[StudyReader] Finalizing message (sendMessage):', {
                    oldId: msg.id,
                    newId,
                    typewriterRunning: !!typewriterRef.current.intervalId,
                    fullTextLength: fullText?.length || 0,
                    finalContentLength: finalContent.length
                  })
                  
                  return {
                    ...msg,
                    id: newId,
                    content: finalContent, // Set full content immediately
                  }
                }
                return msg
              })
            })
          }
        )
      } catch (error) {
        console.error('Error sending message:', error)
        setIsLoading(false)
        setIsStreaming(false)
        
        // Show error message in chat
        setMessages((prev) => {
          const lastStreamingIndex = prev.findLastIndex(
            (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
          )
          
          if (lastStreamingIndex >= 0) {
            // Replace streaming message with error
            const updated = [...prev]
            updated[lastStreamingIndex] = {
              ...updated[lastStreamingIndex],
              id: generateMessageId(), // Finalize ID
              content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
            }
            return updated
          } else {
            // Add error message if no streaming message exists
            return [
              ...prev,
              {
                id: generateMessageId(),
                role: 'assistant',
                content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                timestamp: new Date().toISOString(),
              },
            ]
          }
        })
      }
    },
    [materialId, userId, generateMessageId, startTypewriter, stopTypewriter]
  )

  // Track if we're initializing to prevent double calls
  const isInitializing = useRef(true)

  // Initialize session (page + chat) on first load
  useEffect(() => {
    let isMounted = true

    const initSession = async () => {
      try {
        const session = await getStudySession(materialId, userId)

        if (!isMounted) return

        const initialPage = session.lastPage && session.lastPage > 0 ? session.lastPage : 1

        if (session.messages && session.messages.length > 0) {
          setMessages(session.messages)
        }

        // Set page first
        setCurrentPage(initialPage)
        
        // Mark initialization as complete AFTER setting page
        // This prevents the effect from triggering when handlePageChange calls setCurrentPage
        isInitializing.current = false
        
        // Directly call handlePageChange for initial page with skipStateUpdate=true and isInitialOpen=true
        // This prevents handlePageChange from calling setCurrentPage again (which would trigger the effect)
        // and signals to the backend that this is an initial opening (not just a page change)
        await handlePageChange(initialPage, true, true)
      } catch (error) {
        console.error('[StudyReader] Failed to load study session, falling back to page 1:', error)
        if (!isMounted) return
        
        setCurrentPage(1)
        isInitializing.current = false
        await handlePageChange(1, true, true)
      }
    }

    // Fire and forget; handle errors inside
    initSession()

    return () => {
      isMounted = false
      stopTypewriter()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  // Cleanup typewriter on unmount
  useEffect(() => {
    return () => {
      stopTypewriter()
    }
  }, [stopTypewriter])

  // Handle page change (but not during initial session load)
  useEffect(() => {
    // Skip if we're still initializing (session load in progress)
    if (isInitializing.current) {
      return
    }
    
    if (currentPage > 0) {
      handlePageChange(currentPage)
    }
  }, [currentPage, handlePageChange])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamControllerRef.current) {
        streamControllerRef.current.close()
      }
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [])

  // Log message count and chat width whenever messages change
  useEffect(() => {
    const chatWidth =
      typeof window !== 'undefined' && chatPanelRef.current
        ? chatPanelRef.current.getBoundingClientRect().width
        : null

    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId: 'debug-session',
        runId: 'pre-fix',
        hypothesisId: 'H2',
        location: 'study-reader.tsx:useEffect(messages)',
        message: 'Messages changed, logging count and chat width',
        data: {
          messageCount: messages.length,
          chatWidth,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {})
    // #endregion agent log
  }, [messages.length])

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1)
    }
  }

  const handleNextPage = () => {
    if (currentPage < pageCount) {
      setCurrentPage(currentPage + 1)
    }
  }

  return (
    <div className="flex flex-col h-full max-h-full min-h-0 overflow-hidden">
      <Group
        direction="horizontal"
        className="flex-1 min-h-0 max-h-full overflow-hidden"
        onLayout={(sizes) => {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/97b4ec6b-d4ac-4054-b0d3-ee4550153462', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sessionId: 'debug-session',
              runId: 'pre-fix',
              hypothesisId: 'H1',
              location: 'study-reader.tsx:Group/onLayout',
              message: 'Panel layout sizes updated',
              data: { sizes },
              timestamp: Date.now(),
            }),
          }).catch(() => {})
          // #endregion agent log
        }}
      >
        {/* Left Panel: PDF Viewer */}
        <Panel defaultSize="50" minSize={30}>
          <div className="flex flex-col h-full min-w-0 bg-background">
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handlePreviousPage}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-muted-foreground">
                  Seite {currentPage} von {pageCount}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleNextPage}
                  disabled={currentPage >= pageCount}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <PdfViewer file={pdfUrl} pageNumber={currentPage} />
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-2 bg-border hover:bg-border/80 transition-colors" />

        {/* Right Panel: Chat Interface */}
        <Panel defaultSize="50" minSize={30}>
          <div
            ref={chatPanelRef}
            className="flex h-full w-full min-h-0 min-w-0 overflow-hidden"
          >
            <ChatInterface
              messages={messages}
              onSend={handleSendMessage}
              isLoading={isLoading}
              isStreaming={isStreaming}
              showTools={showTools}
              onToggleTools={(enabled) => {
                setShowTools(enabled)
                localStorage.setItem('study-reader-show-tools', String(enabled))
              }}
            />
          </div>
        </Panel>
      </Group>
    </div>
  )
}
