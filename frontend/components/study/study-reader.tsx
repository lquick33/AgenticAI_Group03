"use client"

import { useState, useRef } from 'react'
import dynamic from 'next/dynamic'
import { Panel, Group, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInterface } from './chat-interface'
import { CongratulationsScreen } from './congratulations-screen'
import { useChatSession } from '@/hooks/use-chat-session'

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
  const [showCongratulations, setShowCongratulations] = useState(false)
  const [showTools, setShowTools] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('study-reader-show-tools')
      return saved === 'true'
    }
    return false
  })
  const chatPanelRef = useRef<HTMLDivElement | null>(null)

  const {
    messages,
    isLoading,
    isStreaming,
    submittingQuizId,
    currentPage,
    handleSendMessage,
    handlePageChange,
    handleQuizComplete
  } = useChatSession(materialId, userId, pageCount)

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      handlePageChange(currentPage - 1)
    }
  }

  const handleNextPage = () => {
    if (currentPage < pageCount) {
      handlePageChange(currentPage + 1)
    } else if (currentPage === pageCount) {
      // Show congratulations screen when user clicks next on last page
      setShowCongratulations(true)
    }
  }

  return (
    <>
      {showCongratulations && (
        <CongratulationsScreen
          materialId={materialId}
          courseId={courseId}
          userId={userId}
          onClose={() => setShowCongratulations(false)}
        />
      )}
      <div className="flex flex-col h-full max-h-full min-h-0 overflow-hidden">
        <Group
        direction="horizontal"
        className="flex-1 min-h-0 max-h-full overflow-hidden"
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
                  variant={currentPage === pageCount ? "default" : "outline"}
                  size="icon"
                  onClick={handleNextPage}
                  disabled={currentPage > pageCount}
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
              onQuizComplete={handleQuizComplete}
              submittingQuizId={submittingQuizId}
            />
          </div>
        </Panel>
      </Group>
    </div>
    </>
  )
}
