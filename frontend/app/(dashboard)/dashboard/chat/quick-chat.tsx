"use client"

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { useQuickChatSession, ViewingMaterial } from '@/hooks/use-quickchat-session'
import { ChatMessage } from '@/components/study/chat-message'
import { Loader } from '@/components/ui/loader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { 
  Search, 
  Send, 
  FileText,
  Loader2,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react'

// Dynamically import PdfViewer to avoid SSR issues
const PdfViewer = dynamic(
  () => import('@/components/study/pdf-viewer').then(mod => mod.PdfViewer),
  { 
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <Loader size={32} />
      </div>
    )
  }
)

interface QuickChatContentProps {
  userId: string
}

export function QuickChatContent({ userId }: QuickChatContentProps) {
  const router = useRouter()
  const [inputValue, setInputValue] = useState('')
  
  // Initialize quick chat session
  // Navigation is handled automatically by the agent through chat confirmation
  const {
    messages,
    isLoading,
    isStreaming,
    sessionState,
    sendMessage,
    setCurrentPage,
  } = useQuickChatSession(userId)
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim() && !isStreaming) {
      sendMessage(inputValue)
      setInputValue('')
    }
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as React.FormEvent)
    }
  }
  
  // Close navigates back to dashboard
  const handleClose = () => {
    router.push('/dashboard')
  }
  
  // Viewing mode: split layout with PDF viewer
  if (sessionState.mode === 'viewing' && sessionState.viewingMaterial) {
    return (
      <ViewingModeContent
        viewingMaterial={sessionState.viewingMaterial}
        messages={messages}
        isLoading={isLoading}
        isStreaming={isStreaming}
        inputValue={inputValue}
        setInputValue={setInputValue}
        handleSubmit={handleSubmit}
        handleKeyDown={handleKeyDown}
        setCurrentPage={setCurrentPage}
        onClose={handleClose}
      />
    )
  }
  
  // Discovery mode: chat interface
  return (
    <DiscoveryModeContent
      messages={messages}
      isLoading={isLoading}
      isStreaming={isStreaming}
      inputValue={inputValue}
      setInputValue={setInputValue}
      handleSubmit={handleSubmit}
      handleKeyDown={handleKeyDown}
    />
  )
}

// Discovery Mode Content (chat only, no separate header)
interface DiscoveryModeContentProps {
  messages: { id: string; role: string; content: string }[]
  isLoading: boolean
  isStreaming: boolean
  inputValue: string
  setInputValue: (value: string) => void
  handleSubmit: (e: React.FormEvent) => void
  handleKeyDown: (e: React.KeyboardEvent) => void
}

function DiscoveryModeContent({
  messages,
  isLoading,
  isStreaming,
  inputValue,
  setInputValue,
  handleSubmit,
  handleKeyDown,
}: DiscoveryModeContentProps) {
  return (
    <div className="flex flex-col h-full bg-[#f6f4f1]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {isLoading && messages.length === 0 ? (
            <div className="flex items-center justify-center py-20">
              <Loader size={32} />
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  id={message.id}
                  role={message.role as 'user' | 'assistant'}
                  content={message.content}
                  isStreaming={isStreaming && message.id === messages[messages.length - 1]?.id && message.role === 'assistant'}
                />
              ))}
            </>
          )}
        </div>
      </div>
      
      {/* Input area */}
      <div className="border-t bg-white px-6 py-4 flex-shrink-0">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nach einem Thema suchen oder eine Frage stellen..."
                className="pl-10 pr-4"
                disabled={isStreaming}
              />
            </div>
            <Button type="submit" disabled={!inputValue.trim() || isStreaming}>
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2 text-center">
            Beispiel: &ldquo;Wo wird Rekursion erklärt?&rdquo; oder &ldquo;Was sind lineare Gleichungssysteme?&rdquo;
          </p>
        </form>
      </div>
    </div>
  )
}

// Viewing Mode Content (split panel with PDF viewer)
interface ViewingModeContentProps {
  viewingMaterial: ViewingMaterial
  messages: { id: string; role: string; content: string }[]
  isLoading: boolean
  isStreaming: boolean
  inputValue: string
  setInputValue: (value: string) => void
  handleSubmit: (e: React.FormEvent) => void
  handleKeyDown: (e: React.KeyboardEvent) => void
  setCurrentPage: (page: number) => void
  onClose: () => void
}

function ViewingModeContent({
  viewingMaterial,
  messages,
  isLoading,
  isStreaming,
  inputValue,
  setInputValue,
  handleSubmit,
  handleKeyDown,
  setCurrentPage,
  onClose,
}: ViewingModeContentProps) {
  const handlePreviousPage = () => {
    if (viewingMaterial.currentPage > 1) {
      setCurrentPage(viewingMaterial.currentPage - 1)
    }
  }
  
  const handleNextPage = () => {
    if (viewingMaterial.currentPage < viewingMaterial.pageCount) {
      setCurrentPage(viewingMaterial.currentPage + 1)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Split panel layout */}
      <PanelGroup orientation="horizontal" className="h-full">
        {/* Left Panel: PDF Viewer */}
        <Panel defaultSize={50} minSize={30}>
          <div className="flex flex-col h-full bg-background">
            {/* PDF Navigation */}
            <div className="flex items-center justify-between p-3 border-b">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handlePreviousPage}
                  disabled={viewingMaterial.currentPage <= 1}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="text-sm font-medium min-w-[100px] text-center">
                  Seite {viewingMaterial.currentPage} / {viewingMaterial.pageCount}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleNextPage}
                  disabled={viewingMaterial.currentPage >= viewingMaterial.pageCount}
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground truncate max-w-[200px]">
                    {viewingMaterial.materialName}
                  </span>
                </div>
                <Button variant="ghost" size="sm" onClick={onClose}>
                  <X className="w-4 h-4 mr-1" />
                  Schließen
                </Button>
              </div>
            </div>
            
            {/* PDF Content */}
            <div className="flex-1 overflow-auto">
              <PdfViewer
                key={`${viewingMaterial.materialId}-${viewingMaterial.currentPage}`}
                file={viewingMaterial.pdfUrl}
                pageNumber={viewingMaterial.currentPage}
              />
            </div>
          </div>
        </Panel>
        
        <PanelResizeHandle className="w-2 bg-border hover:bg-border/80 transition-colors cursor-col-resize" />
        
        {/* Right Panel: Chat */}
        <Panel defaultSize={50} minSize={30}>
          <div className="flex flex-col h-full bg-[#f6f4f1]">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              <div className="space-y-4">
                {isLoading && messages.length === 0 ? (
                  <div className="flex items-center justify-center py-20">
                    <Loader size={32} />
                  </div>
                ) : (
                  <>
                    {messages.map((message) => (
                      <ChatMessage
                        key={message.id}
                        id={message.id}
                        role={message.role as 'user' | 'assistant'}
                        content={message.content}
                        isStreaming={isStreaming && message.id === messages[messages.length - 1]?.id && message.role === 'assistant'}
                      />
                    ))}
                  </>
                )}
              </div>
            </div>
            
            {/* Input area */}
            <div className="border-t bg-white px-4 py-3 flex-shrink-0">
              <form onSubmit={handleSubmit}>
                <div className="flex gap-2">
                  <Input
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Frage zu dieser Seite stellen..."
                    disabled={isStreaming}
                  />
                  <Button type="submit" disabled={!inputValue.trim() || isStreaming}>
                    {isStreaming ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </Panel>
      </PanelGroup>
    </div>
  )
}
