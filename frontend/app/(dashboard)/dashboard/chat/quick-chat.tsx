"use client"

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { useQuickChatSession, ViewingMaterial } from '@/hooks/use-quickchat-session'
import { QuickChatSearchResult } from '@/lib/api/quickchat'
import { ChatMessage } from '@/components/study/chat-message'
import { Loader } from '@/components/ui/loader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Search, 
  Send, 
  ArrowRight,
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
  const {
    messages,
    isLoading,
    isStreaming,
    searchResults,
    sessionState,
    sendMessage,
    openMaterial,
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
        searchResults={searchResults}
        openMaterial={openMaterial}
      />
    )
  }
  
  // Discovery mode: chat interface
  return (
    <DiscoveryModeContent
      messages={messages}
      isLoading={isLoading}
      isStreaming={isStreaming}
      searchResults={searchResults}
      inputValue={inputValue}
      setInputValue={setInputValue}
      handleSubmit={handleSubmit}
      handleKeyDown={handleKeyDown}
      openMaterial={openMaterial}
    />
  )
}

// Discovery Mode Content (chat only, no separate header)
interface DiscoveryModeContentProps {
  messages: { id: string; role: string; content: string }[]
  isLoading: boolean
  isStreaming: boolean
  searchResults: QuickChatSearchResult[]
  inputValue: string
  setInputValue: (value: string) => void
  handleSubmit: (e: React.FormEvent) => void
  handleKeyDown: (e: React.KeyboardEvent) => void
  openMaterial: (result: QuickChatSearchResult) => void
}

function DiscoveryModeContent({
  messages,
  isLoading,
  isStreaming,
  searchResults,
  inputValue,
  setInputValue,
  handleSubmit,
  handleKeyDown,
  openMaterial,
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
              
              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-medium text-muted-foreground mb-3">
                    Gefundene Stellen in deinen Vorlesungen:
                  </h3>
                  <div className="grid gap-3">
                    {searchResults.map((result, index) => (
                      <SearchResultCard
                        key={`${result.material_id}-${result.page_number}`}
                        result={result}
                        index={index + 1}
                        onClick={() => openMaterial(result)}
                      />
                    ))}
                  </div>
                </div>
              )}
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
  searchResults: QuickChatSearchResult[]
  openMaterial: (result: QuickChatSearchResult) => void
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
  searchResults,
  openMaterial,
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
                    
                    {/* Search Results - shown when agent finds other pages */}
                    {searchResults.length > 0 && (
                      <div className="mt-4 p-3 bg-white rounded-lg border">
                        <h4 className="text-sm font-medium text-muted-foreground mb-2">
                          Gefundene Seiten (klicken zum Wechseln):
                        </h4>
                        <div className="grid gap-2">
                          {searchResults.slice(0, 3).map((result, index) => (
                            <SearchResultCard
                              key={`${result.material_id}-${result.page_number}`}
                              result={result}
                              index={index + 1}
                              onClick={() => openMaterial(result)}
                            />
                          ))}
                        </div>
                      </div>
                    )}
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

// Search Result Card Component
interface SearchResultCardProps {
  result: QuickChatSearchResult
  index: number
  onClick: () => void
}

function SearchResultCard({ result, onClick }: SearchResultCardProps) {
  return (
    <Card 
      className="cursor-pointer hover:bg-accent/50 transition-colors"
      onClick={onClick}
    >
      <CardHeader className="py-3 px-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge 
                variant="outline" 
                className="text-xs flex-shrink-0"
                style={{ 
                  borderColor: result.course_color || undefined,
                  color: result.course_color || undefined 
                }}
              >
                {result.course_title}
              </Badge>
              <span className="text-xs text-muted-foreground truncate">
                {result.material_name}
              </span>
            </div>
            <CardTitle className="text-sm font-medium line-clamp-2">
              Seite {result.page_number}
            </CardTitle>
            <CardDescription className="text-xs line-clamp-2 mt-1">
              {result.summary}
            </CardDescription>
            {result.key_terms.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {result.key_terms.slice(0, 5).map((term, i) => (
                  <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0">
                    {term}
                  </Badge>
                ))}
              </div>
            )}
          </div>
          <Button variant="ghost" size="icon" className="flex-shrink-0">
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
    </Card>
  )
}
