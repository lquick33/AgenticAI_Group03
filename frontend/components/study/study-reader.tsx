"use client"

import { useState, useEffect, useRef, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { Panel, Group, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInterface } from './chat-interface'
import { initiateChat, sendMessage } from '@/lib/api/study'
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

  // Generate unique message ID
  const generateMessageId = useCallback(() => {
    messageIdCounter.current += 1
    return `msg-${Date.now()}-${messageIdCounter.current}`
  }, [])

  // Handle page change - initiate chat
  const handlePageChange = useCallback(
    async (newPage: number) => {
      if (newPage < 1 || newPage > pageCount) return

      setCurrentPage(newPage)
      setIsLoading(true)
      setIsStreaming(true)

      // Close existing stream
      if (streamControllerRef.current) {
        streamControllerRef.current.close()
        streamControllerRef.current = null
      }

      // Keep existing messages - don't clear chat history
      // The backend will maintain conversation continuity through the checkpointer

      // Initiate chat for new page
      try {
        console.log('[StudyReader] Initiating chat for page', newPage)
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
            return
          }

          // Handle different chunk structures: chunk.messages or chunk.agent.messages or chunk[node_name].messages
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

              console.log('[StudyReader] Processing message:', msg.role, contentText?.substring(0, 50))
              if (msg.role === 'assistant' && contentText) {
                // Update or add assistant message
                setMessages((prev) => {
                  // Find the last assistant message that is currently streaming (temporary ID)
                  // or the last assistant message if we're updating an existing one
                  const lastStreamingIndex = prev.findLastIndex(
                    (m) => m.role === 'assistant' && m.id.startsWith('streaming-')
                  )

                  if (lastStreamingIndex >= 0) {
                    // Update existing streaming message
                    const updated = [...prev]
                    updated[lastStreamingIndex] = {
                      ...updated[lastStreamingIndex],
                      content: contentText,
                    }
                    console.log('[StudyReader] Updated streaming message at index', lastStreamingIndex)
                    return updated
                  } else {
                    // Check if there's a last assistant message that we should update
                    const lastAssistantIndex = prev.findLastIndex(
                      (m) => m.role === 'assistant'
                    )
                    
                    // Only update if the last assistant message is very recent (within last 2 seconds)
                    // This handles the case where we're continuing a stream
                    if (lastAssistantIndex >= 0) {
                      const lastMsg = prev[lastAssistantIndex]
                      const msgTime = new Date(lastMsg.timestamp).getTime()
                      const now = Date.now()
                      const timeDiff = now - msgTime
                      
                      // If message is very recent (< 2 seconds), update it (likely continuation)
                      if (timeDiff < 2000) {
                        const updated = [...prev]
                        updated[lastAssistantIndex] = {
                          ...updated[lastAssistantIndex],
                          content: contentText,
                        }
                        console.log('[StudyReader] Updated recent message at index', lastAssistantIndex)
                        return updated
                      }
                    }
                    
                    // Add new message for new page response
                    console.log('[StudyReader] Adding new assistant message for page', newPage)
                    return [
                      ...prev,
                      {
                        id: `streaming-${generateMessageId()}`,
                        role: 'assistant',
                        content: contentText,
                        timestamp: new Date().toISOString(),
                      },
                    ]
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
        },
        () => {
          console.log('[StudyReader] Chat stream completed')
          setIsLoading(false)
          setIsStreaming(false)
          
          // Replace streaming message ID with final ID
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id.startsWith('streaming-')
                ? { ...msg, id: generateMessageId() }
                : msg
            )
          )
          
          if (streamControllerRef.current) {
            streamControllerRef.current.close()
            streamControllerRef.current = null
          }
        }
      )

        streamControllerRef.current = streamController
      } catch (error) {
        console.error('Error initiating chat:', error)
        setIsLoading(false)
        setIsStreaming(false)
      }
    },
    [materialId, userId, pageCount, generateMessageId]
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
      setMessages((prev) => [...prev, userMessage])

      setIsLoading(true)
      setIsStreaming(true)

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
              return
            }

            // Handle different chunk structures: chunk.messages or chunk.agent.messages or chunk[node_name].messages
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

                if (msg.role === 'assistant' && contentText) {
                  // Update or add assistant message
                  setMessages((prev) => {
                    const existingIndex = prev.findIndex(
                      (m) => m.role === 'assistant' && m.id.startsWith('temp-')
                    )

                    if (existingIndex >= 0) {
                      // Update existing streaming message
                      const updated = [...prev]
                      updated[existingIndex] = {
                        ...updated[existingIndex],
                        content: contentText,
                      }
                      return updated
                    } else {
                      // Add new message
                      return [
                        ...prev,
                        {
                          id: `temp-${generateMessageId()}`,
                          role: 'assistant',
                          content: contentText,
                          timestamp: new Date().toISOString(),
                        },
                      ]
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
          },
          () => {
            setIsLoading(false)
            setIsStreaming(false)
            // Replace temp message with final message
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id.startsWith('temp-')
                  ? { ...msg, id: generateMessageId() }
                  : msg
              )
            )
          }
        )
      } catch (error) {
        console.error('Error sending message:', error)
        setIsLoading(false)
        setIsStreaming(false)
      }
    },
    [materialId, userId, generateMessageId]
  )

  // Initialize chat on first load
  useEffect(() => {
    handlePageChange(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  // Handle page change (but not on initial mount)
  const isInitialMount = useRef(true)
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false
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
      <Group direction="horizontal" className="flex-1 min-h-0 max-h-full overflow-hidden">
        {/* Left Panel: PDF Viewer */}
        <Panel defaultSize={50} minSize={30}>
          <div className="flex flex-col h-full bg-background">
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
        <Panel defaultSize={50} minSize={30}>
          <div ref={chatPanelRef} className="flex h-full min-h-0 overflow-hidden">
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
