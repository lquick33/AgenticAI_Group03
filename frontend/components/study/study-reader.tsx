"use client"

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import dynamic from 'next/dynamic'
import { Panel, Group, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatInterface } from './chat-interface'
import { CongratulationsScreen } from './congratulations-screen'
import { useChatSession } from '@/hooks/use-chat-session'
import { toast } from 'sonner'
import { createClient } from '@/lib/supabase/client'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Maximum snippets per page (should match backend setting)
const MAX_SNIPPETS_PER_PAGE = 3

// Dynamically import PDF Viewer with SSR disabled
const PdfViewer = dynamic(() => import('./pdf-viewer').then((mod) => ({ default: mod.PdfViewer })), {
  ssr: false,
})

interface Snippet {
  id: string
  page_number: number
  image_path: string
  created_at: string
  order_index?: number
}

interface StudyReaderProps {
  materialId: string
  materialName?: string
  courseId: string
  courseName?: string
  pdfUrl: string
  pageCount: number
  userId: string
  initialPage?: number  // Optional initial page from URL query param (for deep linking from Quick Chat)
}

export function StudyReader({
  materialId,
  materialName,
  courseId,
  courseName,
  pdfUrl,
  pageCount,
  userId,
  initialPage,
}: StudyReaderProps) {
  const [showCongratulations, setShowCongratulations] = useState(false)
  const [showTools, setShowTools] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('study-reader-show-tools')
      return saved === 'true'
    }
    return false
  })
  const [autoExplainOnPageChange, setAutoExplainOnPageChange] = useState(() => {
    // Check localStorage first for immediate value
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('auto_explain_on_page_change')
      if (saved !== null) {
        return saved === 'true'
      }
    }
    return true
  })
  const chatPanelRef = useRef<HTMLDivElement | null>(null)

  // Load user preference for auto-explain on page change from database
  useEffect(() => {
    const loadPreference = async () => {
      const supabase = createClient()
      try {
        const { data: prefs } = await supabase
          .from('user_preferences')
          .select('auto_explain_on_page_change')
          .eq('user_id', userId)
          .single()
        
        if (prefs?.auto_explain_on_page_change !== undefined) {
          setAutoExplainOnPageChange(prefs.auto_explain_on_page_change)
          // Sync to localStorage
          localStorage.setItem('auto_explain_on_page_change', String(prefs.auto_explain_on_page_change))
        }
      } catch (error) {
        // Use default (true) if preference not found
        console.log('[StudyReader] Using default auto-explain setting')
      }
    }
    
    loadPreference()
  }, [userId])

  // Listen for setting changes (when user changes setting in settings dialog)
  useEffect(() => {
    // Cross-tab changes via localStorage
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auto_explain_on_page_change' && e.newValue !== null) {
        setAutoExplainOnPageChange(e.newValue === 'true')
      }
    }
    
    // Same-tab changes via custom event
    const handleCustomEvent = (e: CustomEvent<boolean>) => {
      setAutoExplainOnPageChange(e.detail)
    }
    
    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('autoExplainSettingChanged', handleCustomEvent as EventListener)
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('autoExplainSettingChanged', handleCustomEvent as EventListener)
    }
  }, [])

  const {
    messages,
    isLoading,
    isStreaming,
    submittingQuizId,
    currentPage,
    handleSendMessage,
    handlePageChange,
    handleQuizComplete
  } = useChatSession(materialId, userId, pageCount, initialPage, autoExplainOnPageChange)

  // Track all snippets for the material
  const [allSnippets, setAllSnippets] = useState<Snippet[]>([])
  
  // OPTIMIZED: Derive pageSnippets with useMemo instead of useState + useEffect
  const pageSnippets = useMemo(
    () => allSnippets.filter(s => s.page_number === currentPage),
    [allSnippets, currentPage]
  )

  // Fetch all snippets for material
  const fetchSnippets = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/study/snippets/${materialId}?user_id=${userId}`)
      if (response.ok) {
        const snippets: Snippet[] = await response.json()
        setAllSnippets(snippets)
      }
    } catch (error) {
      console.error('Failed to fetch snippets:', error)
    }
  }, [materialId, userId])

  // Fetch snippets on mount
  useEffect(() => {
    fetchSnippets()
  }, [fetchSnippets])

  // Note: pageSnippets is now derived with useMemo above, no useEffect needed

  const handleSaveSnippet = async (blob: Blob) => {
    // Check if we've reached the limit
    if (pageSnippets.length >= MAX_SNIPPETS_PER_PAGE) {
      toast.error(`Maximal ${MAX_SNIPPETS_PER_PAGE} Snippets pro Seite erlaubt`)
      return
    }

    try {
      const formData = new FormData()
      formData.append('file', blob)
      formData.append('course_material_id', materialId)
      formData.append('page_number', currentPage.toString())
      formData.append('user_id', userId)

      const response = await fetch(`${API_URL}/api/study/snippets`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || 'Failed to save snippet')
      }
      
      // Refresh snippets list
      await fetchSnippets()
      
      const newCount = pageSnippets.length + 1
      toast.success(`Snippet ${newCount} für Seite ${currentPage} gespeichert`)
    } catch (error) {
      console.error('Error saving snippet:', error)
      toast.error(error instanceof Error ? error.message : 'Fehler beim Speichern des Snippets')
    }
  }

  const handleDeleteSnippet = async (snippetId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/study/snippets/${snippetId}?user_id=${userId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete snippet')
      }
      
      // Refresh snippets list
      await fetchSnippets()
      toast.success('Snippet gelöscht')
    } catch (error) {
      console.error('Error deleting snippet:', error)
      toast.error('Fehler beim Löschen des Snippets')
    }
  }

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
          materialName={materialName}
          courseId={courseId}
          courseName={courseName}
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
              <PdfViewer 
                file={pdfUrl} 
                pageNumber={currentPage} 
                onSaveSnippet={handleSaveSnippet}
                snippets={pageSnippets}
                maxSnippets={MAX_SNIPPETS_PER_PAGE}
                onDeleteSnippet={handleDeleteSnippet}
              />
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
