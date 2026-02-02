import { useState, useRef, useCallback, useEffect } from 'react'
import { initiateChat, sendMessage, getStudySession, submitQuiz, saveCurrentPage } from '@/lib/api/study'
import { parseQuizToolResponse } from '@/lib/quiz-validation'
import { EventQueue } from '@/lib/event-queue'
import type { ChatMessage, ToolCall } from '@/types'
import { useTypewriter } from './use-typewriter'

export function useChatSession(
  materialId: string,
  userId: string,
  pageCount: number,
  urlInitialPage?: number,  // Optional initial page from URL query param (overrides session lastPage)
  autoExplainOnPageChange: boolean = true  // When false, AI only responds to user messages
) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [submittingQuizId, setSubmittingQuizId] = useState<string | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  
  const streamControllerRef = useRef<{ close: () => void } | null>(null)
  const messageIdCounter = useRef(0)
  const eventQueueRef = useRef<EventQueue>(new EventQueue())
  
  // Use ref for autoExplainOnPageChange to avoid re-initializing when preference loads
  const autoExplainRef = useRef(autoExplainOnPageChange)
  autoExplainRef.current = autoExplainOnPageChange
  
  // Debouncing and request tracking for page changes
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)
  const currentRequestIdRef = useRef<string | null>(null)
  const pageChangeHistoryRef = useRef<Array<{ page: number; timestamp: number }>>([])
  
  // Separate debounce timer for page saving (independent of chat initiation)
  const pageSaveTimerRef = useRef<NodeJS.Timeout | null>(null)
  const lastSavedPageRef = useRef<number | null>(null)
  
  // Use typewriter hook
  const { startTypewriter, stopTypewriter, typewriterRef } = useTypewriter(setMessages)

  // Generate unique message ID
  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1
    return `msg-${Date.now()}-${messageIdCounter.current}`
  }, [])

  // Helper: Clean JSON string
  const cleanJsonString = useCallback((str: string): string => {
    let cleaned = str.trim()
    cleaned = cleaned.replace(/^```(?:json)?\s*\n?/i, '')
    cleaned = cleaned.replace(/\n?```\s*$/i, '')
    cleaned = cleaned.trim()
    return cleaned
  }, [])

  // Process Quiz Tool Response
  const processQuizToolResponse = useCallback((
    toolCallId: string,
    result: string,
    messageId: string,
    currentMessages: ChatMessage[]
  ): ChatMessage[] => {
    const messageIndex = currentMessages.findIndex(m => m.id === messageId)
    if (messageIndex < 0) return currentMessages
    
    const updated = [...currentMessages]
    const message = updated[messageIndex]
    
    if (!message.toolCalls) return currentMessages
    
    const toolCall = message.toolCalls.find(tc => tc.id === toolCallId)
    if (!toolCall || toolCall.name !== 'create_quiz') {
      updated[messageIndex] = {
        ...message,
        toolCalls: message.toolCalls.map(tc => 
          tc.id === toolCallId
            ? { ...tc, result, state: 'completed' as const }
            : tc
        ),
      }
      return updated
    }
    
    try {
      const cleanedResult = cleanJsonString(result)
      const resultData = JSON.parse(cleanedResult)
      
      if (resultData.error) {
        const errorMessage = resultData.error || 'Quiz-Erstellung fehlgeschlagen'
        console.error('[useChatSession] Quiz creation failed:', errorMessage, resultData)
        
        updated[messageIndex] = {
          ...message,
          toolCalls: message.toolCalls.map(tc => 
            tc.id === toolCallId
              ? { ...tc, result, state: 'completed' as const, error: errorMessage }
              : tc
          ),
        }
        return updated
      }
      
      const validatedData = parseQuizToolResponse(cleanedResult)
      
      updated[messageIndex] = {
        ...message,
        toolCalls: message.toolCalls.map(tc => 
          tc.id === toolCallId
            ? { ...tc, result, state: 'completed' as const }
            : tc
        ),
        quiz: {
          quiz_id: validatedData.quiz_id,
          topic: validatedData.topic || validatedData.quiz_data.topic,
          questions: validatedData.quiz_data.questions || []
        }
      }
      
      console.log('[useChatSession] Quiz added to message:', validatedData.quiz_id)
      return updated
      
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Failed to parse quiz result'
      console.error('[useChatSession] Failed to parse/validate quiz result:', errorMessage, e)
      
      updated[messageIndex] = {
        ...message,
        toolCalls: message.toolCalls.map(tc => 
          tc.id === toolCallId
            ? { ...tc, result, state: 'completed' as const, error: errorMessage }
            : tc
        ),
      }
      return updated
    }
  }, [cleanJsonString])

  // Initiate chat for page
  const initiateChatForPage = useCallback(
    async (page: number, requestId: string, isInitialOpen: boolean = false) => {
      stopTypewriter()

      if (streamControllerRef.current) {
        streamControllerRef.current.close()
        streamControllerRef.current = null
      }

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
        console.log('[useChatSession] Initiating chat for page', page, 'requestId:', requestId)
        const streamController = await initiateChat(
          materialId,
          page,
          userId,
          (chunk) => {
            if (currentRequestIdRef.current !== requestId) return

            if (chunk.error) {
              console.error('[useChatSession] Chat error:', chunk.error)
              setIsLoading(false)
              setIsStreaming(false)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    id: generateMessageId(),
                    content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                  }
                  return updated
                } else {
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
              const retryableEvents = eventQueueRef.current.add(chunk)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const messageId = prev[lastStreamingIndex].id
                  const toolCallsWithState = (chunk.tool_calls || []).map(tc => ({
                    ...tc,
                    state: tc.result ? (tc.state || 'completed') : 'running' as const
                  }))
                  
                  let updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    toolCalls: [...(updated[lastStreamingIndex].toolCalls || []), ...toolCallsWithState],
                  }
                  
                  if (retryableEvents.length > 0) {
                    retryableEvents.forEach(retryEvent => {
                      if (retryEvent.type === 'tool_response' && retryEvent.tool_call_id && retryEvent.result) {
                        updated = processQuizToolResponse(
                          retryEvent.tool_call_id,
                          retryEvent.result,
                          messageId,
                          updated
                        )
                      }
                    })
                  }
                  
                  return updated
                }
                return prev
              })
              return
            }

            // Handle tool response events
            if (chunk.type === 'tool_response' && chunk.tool_call_id && chunk.result) {
              if (!eventQueueRef.current.validateOrder(chunk)) {
                eventQueueRef.current.add(chunk)
                return
              }
              
              eventQueueRef.current.add(chunk)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const messageId = prev[lastStreamingIndex].id
                  return processQuizToolResponse(
                    chunk.tool_call_id!,
                    chunk.result!,
                    messageId,
                    prev
                  )
                }
                return prev
              })
              return
            }

            // Handle delta events
            if (chunk.type === 'delta' && chunk.role === 'assistant' && chunk.delta) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )

                let streamingMessageId: string
                let newContent: string

                if (lastStreamingIndex >= 0) {
                  streamingMessageId = prev[lastStreamingIndex].id
                  newContent = (prev[lastStreamingIndex].content || '') + chunk.delta
                  
                  startTypewriter(newContent, streamingMessageId, 40)
                  
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    content: newContent,
                  }
                  return updated
                } else {
                  streamingMessageId = `streaming-${generateMessageId()}`
                  newContent = chunk.delta
                  
                  startTypewriter(newContent, streamingMessageId, 40)
                  
                  return [
                    ...prev,
                    {
                      id: streamingMessageId,
                      role: 'assistant',
                      content: newContent,
                      timestamp: new Date().toISOString(),
                    },
                  ]
                }
              })
              return
            }

            // Handle regular message chunks
            let messages: Array<{ role: string; content: any }> = []
            if (chunk.messages) {
              messages = chunk.messages
            } else {
              for (const key in chunk) {
                // @ts-ignore
                if (key !== 'tools' && chunk[key] && chunk[key].messages && Array.isArray(chunk[key].messages)) {
                  // @ts-ignore
                  messages = chunk[key].messages
                  break
                }
              }
            }

            if (messages.length > 0) {
              messages.forEach((msg) => {
                let contentText = ''
                if (typeof msg.content === 'string') {
                  contentText = msg.content
                } else if (Array.isArray(msg.content)) {
                  contentText = msg.content
                    .map((item: any) => {
                      if (typeof item === 'string') return item
                      if (item && typeof item === 'object') return item.text || item.content || ''
                      return ''
                    })
                    .filter((text: string) => text)
                    .join('')
                } else if (msg.content && typeof msg.content === 'object') {
                  // @ts-ignore
                  contentText = msg.content.text || msg.content.content || JSON.stringify(msg.content)
                }

                if (msg.role === 'assistant' && contentText) {
                  setMessages((prev) => {
                    const lastStreamingIndex = prev.findLastIndex(
                      (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                    )

                    let streamingMessageId: string

                    if (lastStreamingIndex >= 0) {
                      streamingMessageId = prev[lastStreamingIndex].id
                      startTypewriter(contentText, streamingMessageId, 40)
                      return prev
                    } else {
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
                      startTypewriter(contentText, newId, 40)
                      return updated
                    }
                  })
                }
              })
            }
          },
          (error) => {
            if (currentRequestIdRef.current !== requestId) return
            console.error('[useChatSession] Chat initiation error:', error)
            setIsLoading(false)
            setIsStreaming(false)
            
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                const updated = [...prev]
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  id: generateMessageId(),
                  content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
                }
                return updated
              } else {
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
            if (currentRequestIdRef.current !== requestId) return
            console.log('[useChatSession] Chat stream completed for request:', requestId)
            setIsLoading(false)
            setIsStreaming(false)
            
            const fullText = typewriterRef.current.fullText
            
            setMessages((prev) => {
              return prev.map((msg) => {
                if (msg.id.startsWith('streaming-')) {
                  const newId = generateMessageId()
                  if (typewriterRef.current.messageId === msg.id) {
                    typewriterRef.current.messageId = newId
                  }
                  
                  const finalContent = fullText || typewriterRef.current.fullText || msg.content || ''
                  
                  return {
                    ...msg,
                    id: newId,
                    content: finalContent,
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
        if (currentRequestIdRef.current !== requestId) return
        console.error('Error initiating chat:', error)
        setIsLoading(false)
        setIsStreaming(false)
        
        setMessages((prev) => {
          const lastStreamingIndex = prev.findLastIndex(
            (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
          )
          
          if (lastStreamingIndex >= 0) {
            const updated = [...prev]
            updated[lastStreamingIndex] = {
              ...updated[lastStreamingIndex],
              id: generateMessageId(),
              content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut oder blättere zur nächsten Seite.',
            }
            return updated
          } else {
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
    [materialId, userId, generateMessageId, startTypewriter, stopTypewriter, processQuizToolResponse]
  )

  // Handle page change
  const handlePageChange = useCallback(
    async (newPage: number, skipStateUpdate: boolean = false, isInitialOpen: boolean = false) => {
      if (newPage < 1 || newPage > pageCount) return

      if (!skipStateUpdate) {
        setCurrentPage(newPage)
      }

      // Save page (debounced, independent of auto-explain)
      // Skip during initial load (isInitialOpen) - don't overwrite saved page with initial state
      // Skip if this is the same page we just saved
      if (!isInitialOpen && lastSavedPageRef.current !== newPage) {
        if (pageSaveTimerRef.current) {
          clearTimeout(pageSaveTimerRef.current)
        }
        pageSaveTimerRef.current = setTimeout(() => {
          lastSavedPageRef.current = newPage
          saveCurrentPage(materialId, userId, newPage)
        }, 1000) // 1 second debounce for page save
      }

      // Skip auto-explain if setting is disabled (but always allow initial open)
      if (!autoExplainRef.current && !isInitialOpen) {
        console.log('[useChatSession] Auto-explain disabled, skipping chat initiation for page', newPage)
        return
      }

      const now = Date.now()
      pageChangeHistoryRef.current.push({ page: newPage, timestamp: now })
      
      pageChangeHistoryRef.current = pageChangeHistoryRef.current
        .filter((entry) => now - entry.timestamp < 2000)
        .slice(-5)

      const recentChanges = pageChangeHistoryRef.current.filter(
        (entry) => now - entry.timestamp < 1000
      )
      const isFastScrolling = recentChanges.length > 3

      if (isFastScrolling && !isInitialOpen) {
        console.log('[useChatSession] Fast scrolling detected, skipping chat initiation for page', newPage)
        setMessages((prev) => {
          return prev.filter((msg) => !msg.id.startsWith('streaming-'))
        })
        setIsLoading(false)
        setIsStreaming(false)
        return
      }

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
        debounceTimerRef.current = null
      }

      const requestId = `req-${Date.now()}-${newPage}-${Math.random().toString(36).substr(2, 9)}`
      currentRequestIdRef.current = requestId

      debounceTimerRef.current = setTimeout(async () => {
        if (currentRequestIdRef.current !== requestId) return
        await initiateChatForPage(newPage, requestId, isInitialOpen)
      }, 500)
    },
    [pageCount, initiateChatForPage, materialId, userId]
  )

  // Handle send message
  const handleSendMessage = useCallback(
    async (message: string) => {
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      }
      
      const placeholderAssistant: ChatMessage = {
        id: `streaming-${generateMessageId()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }
      
      setMessages((prev) => [...prev, userMessage, placeholderAssistant])

      setIsLoading(true)
      setIsStreaming(true)
      stopTypewriter()

      try {
        // Pass current page to ensure agent knows which page user is viewing
        await sendMessage(
          materialId,
          message,
          userId,
          (chunk) => {
            if (chunk.error) {
              console.error('Chat error:', chunk.error)
              setIsLoading(false)
              setIsStreaming(false)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    id: generateMessageId(),
                    content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                  }
                  return updated
                } else {
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

            // Handle tool calls
            if (chunk.type === 'tool_call' && chunk.tool_calls) {
              const retryableEvents = eventQueueRef.current.add(chunk)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const messageId = prev[lastStreamingIndex].id
                  const toolCallsWithState = (chunk.tool_calls || []).map(tc => ({
                    ...tc,
                    state: tc.result ? (tc.state || 'completed') : 'running' as const
                  }))
                  
                  let updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    toolCalls: [...(updated[lastStreamingIndex].toolCalls || []), ...toolCallsWithState],
                  }
                  
                  if (retryableEvents.length > 0) {
                    retryableEvents.forEach(retryEvent => {
                      if (retryEvent.type === 'tool_response' && retryEvent.tool_call_id && retryEvent.result) {
                        updated = processQuizToolResponse(
                          retryEvent.tool_call_id,
                          retryEvent.result,
                          messageId,
                          updated
                        )
                      }
                    })
                  }
                  
                  return updated
                }
                return prev
              })
              return
            }

            // Handle tool responses
            if (chunk.type === 'tool_response' && chunk.tool_call_id && chunk.result) {
              if (!eventQueueRef.current.validateOrder(chunk)) {
                eventQueueRef.current.add(chunk)
                return
              }
              
              eventQueueRef.current.add(chunk)
              
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )
                
                if (lastStreamingIndex >= 0) {
                  const messageId = prev[lastStreamingIndex].id
                  return processQuizToolResponse(
                    chunk.tool_call_id!,
                    chunk.result!,
                    messageId,
                    prev
                  )
                }
                return prev
              })
              return
            }

            // Handle delta
            if (chunk.type === 'delta' && chunk.role === 'assistant' && chunk.delta) {
              setMessages((prev) => {
                const lastStreamingIndex = prev.findLastIndex(
                  (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                )

                let streamingMessageId: string
                let newContent: string

                if (lastStreamingIndex >= 0) {
                  streamingMessageId = prev[lastStreamingIndex].id
                  newContent = (prev[lastStreamingIndex].content || '') + chunk.delta
                  
                  startTypewriter(newContent, streamingMessageId, 40)
                  
                  const updated = [...prev]
                  updated[lastStreamingIndex] = {
                    ...updated[lastStreamingIndex],
                    content: newContent,
                  }
                  return updated
                } else {
                  streamingMessageId = `streaming-${generateMessageId()}`
                  newContent = chunk.delta
                  
                  startTypewriter(newContent, streamingMessageId, 40)
                  
                  return [
                    ...prev,
                    {
                      id: streamingMessageId,
                      role: 'assistant',
                      content: newContent,
                      timestamp: new Date().toISOString(),
                    },
                  ]
                }
              })
              return
            }

            // Handle messages
            let messages: Array<{ role: string; content: any }> = []
            if (chunk.messages) {
              messages = chunk.messages
            } else {
              for (const key in chunk) {
                // @ts-ignore
                if (key !== 'tools' && chunk[key] && chunk[key].messages && Array.isArray(chunk[key].messages)) {
                  // @ts-ignore
                  messages = chunk[key].messages
                  break
                }
              }
            }

            if (messages.length > 0) {
              messages.forEach((msg) => {
                let contentText = ''
                if (typeof msg.content === 'string') {
                  contentText = msg.content
                } else if (Array.isArray(msg.content)) {
                  contentText = msg.content
                    .map((item: any) => {
                      if (typeof item === 'string') return item
                      if (item && typeof item === 'object') return item.text || item.content || ''
                      return ''
                    })
                    .filter((text: string) => text)
                    .join('')
                } else if (msg.content && typeof msg.content === 'object') {
                  // @ts-ignore
                  contentText = msg.content.text || msg.content.content || JSON.stringify(msg.content)
                }

                if (msg.role === 'assistant' && contentText) {
                  setMessages((prev) => {
                    const lastStreamingIndex = prev.findLastIndex(
                      (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                    )

                    let streamingMessageId: string

                    if (lastStreamingIndex >= 0) {
                      streamingMessageId = prev[lastStreamingIndex].id
                      startTypewriter(contentText, streamingMessageId, 40)
                      return prev
                    } else {
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
            
            setMessages((prev) => {
              const lastStreamingIndex = prev.findLastIndex(
                (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
              )
              
              if (lastStreamingIndex >= 0) {
                const updated = [...prev]
                updated[lastStreamingIndex] = {
                  ...updated[lastStreamingIndex],
                  id: generateMessageId(),
                  content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
                }
                return updated
              } else {
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
            console.log('[useChatSession] Send message stream completed')
            setIsLoading(false)
            setIsStreaming(false)
            
            const fullText = typewriterRef.current.fullText
            
            setMessages((prev) => {
              return prev.map((msg) => {
                if (msg.id.startsWith('streaming-')) {
                  const newId = generateMessageId()
                  if (typewriterRef.current.messageId === msg.id) {
                    typewriterRef.current.messageId = newId
                  }
                  
                  const finalContent = fullText || typewriterRef.current.fullText || msg.content || ''
                  
                  return {
                    ...msg,
                    id: newId,
                    content: finalContent,
                  }
                }
                return msg
              })
            })
          },
          currentPage  // Pass current page so agent knows which page user is viewing
        )
      } catch (error) {
        console.error('Error sending message:', error)
        setIsLoading(false)
        setIsStreaming(false)
        
        setMessages((prev) => {
          const lastStreamingIndex = prev.findLastIndex(
            (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
          )
          
          if (lastStreamingIndex >= 0) {
            const updated = [...prev]
            updated[lastStreamingIndex] = {
              ...updated[lastStreamingIndex],
              id: generateMessageId(),
              content: 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
            }
            return updated
          } else {
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
    [materialId, userId, currentPage, generateMessageId, startTypewriter, stopTypewriter, processQuizToolResponse]
  )

  // Handle quiz complete
  const handleQuizComplete = useCallback(async (
    quizId: string,
    answers: Record<string, 'A' | 'B' | 'C' | 'D'>
  ) => {
    try {
      setSubmittingQuizId(quizId)
      
      const result = await submitQuiz(quizId, answers, userId)
      
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.quiz && msg.quiz.quiz_id === quizId && msg.toolCalls) {
            return {
              ...msg,
              toolCalls: msg.toolCalls.map((tc) => 
                tc.name === 'create_quiz' && tc.state !== 'completed'
                  ? { ...tc, state: 'completed' as const }
                  : tc
              )
            }
          }
          return msg
        })
      })
      
      if (result.tutor_feedback) {
        const feedbackMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'assistant',
          content: result.tutor_feedback,
          timestamp: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, feedbackMessage])
      }
      
    } catch (error) {
      console.error('Failed to submit quiz:', error)
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'assistant',
        content: 'Entschuldigung, beim Speichern der Quiz-Ergebnisse ist ein Fehler aufgetreten. Bitte versuche es erneut.',
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setSubmittingQuizId(null)
    }
  }, [userId, generateMessageId])

  // Refs for stable function references in effects
  const handlePageChangeRef = useRef(handlePageChange)
  handlePageChangeRef.current = handlePageChange
  const stopTypewriterRef = useRef(stopTypewriter)
  stopTypewriterRef.current = stopTypewriter

  // Initialization effect - runs when material/user changes
  const isInitializing = useRef(true)
  
  useEffect(() => {
    // Reset state for new initialization
    isInitializing.current = true
    console.log('[useChatSession] Starting initialization for material:', materialId)
    
    let isMounted = true
    const initSession = async () => {
      try {
        const session = await getStudySession(materialId, userId)
        console.log('[useChatSession] Loaded session:', { lastPage: session.lastPage, messageCount: session.messages?.length })
        if (!isMounted) return

        // Use URL initial page if provided, otherwise use session's lastPage
        const sessionPage = session.lastPage && session.lastPage > 0 ? session.lastPage : 1
        const initialPage = urlInitialPage && urlInitialPage > 0 && urlInitialPage <= pageCount 
          ? urlInitialPage 
          : sessionPage
        
        console.log('[useChatSession] Computed initialPage:', { sessionPage, urlInitialPage, pageCount, initialPage })
        
        if (session.messages && session.messages.length > 0) {
          setMessages(session.messages)
        }

        setCurrentPage(initialPage)
        // Mark this page as already saved so we don't re-save it immediately
        lastSavedPageRef.current = initialPage
        isInitializing.current = false
        await handlePageChangeRef.current(initialPage, true, true)
      } catch (error) {
        console.error('[useChatSession] Failed to load study session:', error)
        if (!isMounted) return
        // Use URL initial page if provided, otherwise default to 1
        const fallbackPage = urlInitialPage && urlInitialPage > 0 && urlInitialPage <= pageCount 
          ? urlInitialPage 
          : 1
        setCurrentPage(fallbackPage)
        isInitializing.current = false
        await handlePageChangeRef.current(fallbackPage, true, true)
      }
    }
    initSession()
    return () => {
      isMounted = false
      stopTypewriterRef.current()
      if (streamControllerRef.current) streamControllerRef.current.close()
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
      if (pageSaveTimerRef.current) clearTimeout(pageSaveTimerRef.current)
    }
  }, [materialId, userId, urlInitialPage, pageCount])

  // Page change effect
  useEffect(() => {
    if (isInitializing.current) return
    if (currentPage > 0) handlePageChangeRef.current(currentPage)
  }, [currentPage])

  // Save page on tab close/navigation away
  const currentPageRef = useRef(currentPage)
  currentPageRef.current = currentPage
  
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Only save if we've finished initializing (don't save default page 1)
      if (isInitializing.current) return
      
      // Use sendBeacon for reliable save on page unload
      const data = JSON.stringify({
        material_id: materialId,
        user_id: userId,
        page: currentPageRef.current,
      })
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      navigator.sendBeacon(`${API_URL}/api/study/save-page`, new Blob([data], { type: 'application/json' }))
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      // Only save on unmount if we've finished initializing
      if (!isInitializing.current) {
        saveCurrentPage(materialId, userId, currentPageRef.current)
      }
    }
  }, [materialId, userId])

  return {
    messages,
    setMessages,
    isLoading,
    isStreaming,
    submittingQuizId,
    currentPage,
    setCurrentPage,
    handleSendMessage,
    handlePageChange,
    handleQuizComplete
  }
}
