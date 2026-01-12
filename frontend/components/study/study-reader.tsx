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

      // Initiate chat for new page
      try {
        const streamController = await initiateChat(
        materialId,
        newPage,
        userId,
        (chunk) => {
          if (chunk.error) {
            console.error('Chat error:', chunk.error)
            setIsLoading(false)
            setIsStreaming(false)
            return
          }

          if (chunk.messages) {
            chunk.messages.forEach((msg) => {
              if (msg.role === 'assistant' && msg.content) {
                // Update or add assistant message
                setMessages((prev) => {
                  const existingIndex = prev.findIndex(
                    (m) => m.role === 'assistant' && !m.id.startsWith('temp-')
                  )

                  if (existingIndex >= 0) {
                    // Update existing message
                    const updated = [...prev]
                    updated[existingIndex] = {
                      ...updated[existingIndex],
                      content: msg.content,
                    }
                    return updated
                  } else {
                    // Add new message
                    return [
                      ...prev,
                      {
                        id: generateMessageId(),
                        role: 'assistant',
                        content: msg.content,
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
          console.error('Chat initiation error:', error)
          setIsLoading(false)
          setIsStreaming(false)
        },
        () => {
          setIsLoading(false)
          setIsStreaming(false)
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

            if (chunk.messages) {
              chunk.messages.forEach((msg) => {
                if (msg.role === 'assistant' && msg.content) {
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
                        content: msg.content,
                      }
                      return updated
                    } else {
                      // Add new message
                      return [
                        ...prev,
                        {
                          id: `temp-${generateMessageId()}`,
                          role: 'assistant',
                          content: msg.content,
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
    <div className="flex flex-col h-full">
      <Group direction="horizontal" className="flex-1">
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
          <ChatInterface
            messages={messages}
            onSend={handleSendMessage}
            isLoading={isLoading}
            isStreaming={isStreaming}
          />
        </Panel>
      </Group>
    </div>
  )
}
