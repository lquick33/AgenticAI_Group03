"use client"

import { useState, useEffect, useRef, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { Panel, Group, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInterface } from './chat-interface'
import { initiateChat, sendMessage, getStudySession } from '@/lib/api/study'
import type { ChatMessage } from '@/types'

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
  const streamControllerRef = useRef<{ close: () => void } | null>(null)
  const messageIdCounter = useRef(0)
  const chatPanelRef = useRef<HTMLDivElement | null>(null)
  
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
  const startTypewriter = useCallback((fullText: string, messageId: string, speed: number = 20) => {
    // Stop any existing typewriter
    stopTypewriter()

    // Initialize typewriter state
    typewriterRef.current.fullText = fullText
    typewriterRef.current.currentIndex = 0
    typewriterRef.current.messageId = messageId

    // Start animation
    typewriterRef.current.intervalId = setInterval(() => {
      const { fullText, currentIndex, messageId: msgId } = typewriterRef.current

      if (currentIndex >= fullText.length) {
        // Animation complete
        stopTypewriter()
        return
      }

      // Increment index (show 1-3 characters at a time for smoother effect)
      const charsPerStep = Math.min(2, fullText.length - currentIndex)
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

  // Handle page change - initiate chat
  const handlePageChange = useCallback(
    async (newPage: number, skipStateUpdate: boolean = false, isInitialOpen: boolean = false) => {
      if (newPage < 1 || newPage > pageCount) return

      // Only update state if not explicitly skipped (to prevent double triggers during init)
      // React will optimize if the value hasn't actually changed
      if (!skipStateUpdate) {
        setCurrentPage(newPage)
      }
      setIsLoading(true)
      setIsStreaming(true)

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

      // Keep existing messages - don't clear chat history
      // The backend will maintain conversation continuity through the checkpointer

      // Initiate chat for new page
      try {
        console.log('[StudyReader] Initiating chat for page', newPage, 'isInitialOpen:', isInitialOpen)
        const streamController = await initiateChat(
        materialId,
        newPage,
        userId,
        (chunk) => {
          console.log('[StudyReader] Received chunk:', chunk)
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
                    
                    // Always update typewriter with the latest full text
                    if (typewriterRef.current.messageId === streamingMessageId) {
                      // Update the full text - typewriter will continue animating
                      typewriterRef.current.fullText = contentText
                      console.log('[StudyReader] Updated typewriter fullText, length:', contentText.length)
                    } else {
                      // Start typewriter if not running for this message
                      console.log('[StudyReader] Starting typewriter for existing message, length:', contentText.length)
                      startTypewriter(contentText, streamingMessageId, 20)
                    }
                    
                    return prev
                  } else {
                    // Create new streaming message
                    console.log('[StudyReader] Adding new assistant message for page', newPage, 'length:', contentText.length)
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
                    // Start typewriter with the full text
                    startTypewriter(contentText, newId, 20)
                    return updated
                  }
                })
              }
            })
          }
        },
        (error) => {
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
          console.log('[StudyReader] Chat stream completed')
          setIsLoading(false)
          setIsStreaming(false)
          
          // Ensure typewriter completes and finalize message ID
          // First, get the last received content from the typewriter ref
          const lastFullText = typewriterRef.current.fullText
          
          setMessages((prev) => {
            return prev.map((msg) => {
              if (msg.id.startsWith('streaming-')) {
                // Stop typewriter and ensure full content is displayed
                stopTypewriter()
                
                // Use fullText from typewriter if available, otherwise use current content
                // If neither is available, something went wrong - but we should have content
                const finalContent = lastFullText || typewriterRef.current.fullText || msg.content || ''
                
                console.log('[StudyReader] Finalizing message:', {
                  messageId: msg.id,
                  typewriterMessageId: typewriterRef.current.messageId,
                  lastFullTextLength: lastFullText?.length || 0,
                  currentContentLength: msg.content?.length || 0,
                  finalContentLength: finalContent.length
                })
                
                return {
                  ...msg,
                  id: generateMessageId(),
                  content: finalContent, // Always use the full text
                }
              }
              return msg
            })
          })
          
          // Stop any remaining typewriter
          stopTypewriter()
          
          if (streamControllerRef.current) {
            streamControllerRef.current.close()
            streamControllerRef.current = null
          }
        },
        isInitialOpen
      )

        streamControllerRef.current = streamController
      } catch (error) {
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
    [materialId, userId, pageCount, generateMessageId, startTypewriter, stopTypewriter]
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
                      
                      // Always update typewriter with the latest full text
                      if (typewriterRef.current.messageId === streamingMessageId) {
                        // Update the full text - typewriter will continue animating
                        typewriterRef.current.fullText = contentText
                        console.log('[StudyReader] Updated typewriter fullText (sendMessage), length:', contentText.length)
                      } else {
                        // Start typewriter if not running for this message
                        console.log('[StudyReader] Starting typewriter for existing message (sendMessage), length:', contentText.length)
                        startTypewriter(contentText, streamingMessageId, 20)
                      }
                      
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
                      // Start typewriter with the full text
                      startTypewriter(contentText, newId, 20)
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
            
            // Ensure typewriter completes and finalize message ID
            // First, get the last received content from the typewriter ref
            const lastFullText = typewriterRef.current.fullText
            
            setMessages((prev) => {
              return prev.map((msg) => {
                if (msg.id.startsWith('streaming-')) {
                  // Stop typewriter and ensure full content is displayed
                  stopTypewriter()
                  
                  // Use fullText from typewriter if available, otherwise use current content
                  const finalContent = lastFullText || typewriterRef.current.fullText || msg.content || ''
                  
                  console.log('[StudyReader] Finalizing message (sendMessage):', {
                    messageId: msg.id,
                    typewriterMessageId: typewriterRef.current.messageId,
                    lastFullTextLength: lastFullText?.length || 0,
                    currentContentLength: msg.content?.length || 0,
                    finalContentLength: finalContent.length
                  })
                  
                  return {
                    ...msg,
                    id: generateMessageId(),
                    content: finalContent, // Always use the full text
                  }
                }
                return msg
              })
            })
            
            // Stop any remaining typewriter
            stopTypewriter()
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
            />
          </div>
        </Panel>
      </Group>
    </div>
  )
}
