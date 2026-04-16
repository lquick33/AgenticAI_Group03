"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import {
  Group as PanelGroup,
  Panel,
  Separator as PanelResizeHandle,
} from "react-resizable-panels"
import { ChevronLeft, ChevronRight, FileText } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { useChatSession } from "@/hooks/use-chat-session"
import { getApiUrl } from "@/lib/public-env"
import { createClient } from "@/lib/supabase/client"
import { ChatInterface } from "./chat-interface"
import { CongratulationsScreen } from "./congratulations-screen"

const API_URL = getApiUrl()
const MAX_SNIPPETS_PER_PAGE = 3

const PdfViewer = dynamic(
  () => import("./pdf-viewer").then((mod) => ({ default: mod.PdfViewer })),
  {
    ssr: false,
  }
)

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
  initialPage?: number
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
  const [showTools, setShowTools] = useState(false)
  const [autoExplainOnPageChange, setAutoExplainOnPageChange] = useState(true)
  const [allSnippets, setAllSnippets] = useState<Snippet[]>([])

  useEffect(() => {
    const savedTools = localStorage.getItem("study-reader-show-tools")
    if (savedTools === "true") {
      setShowTools(true)
    }
    
    const savedAutoExplain = localStorage.getItem("auto_explain_on_page_change")
    if (savedAutoExplain !== null) {
      setAutoExplainOnPageChange(savedAutoExplain === "true")
    }
  }, [])

  useEffect(() => {
    const loadPreference = async () => {
      const supabase = createClient()
      try {
        const { data: prefs } = await supabase
          .from("user_preferences")
          .select("auto_explain_on_page_change")
          .eq("user_id", userId)
          .single()

        if (prefs?.auto_explain_on_page_change !== undefined) {
          setAutoExplainOnPageChange(prefs.auto_explain_on_page_change)
          localStorage.setItem(
            "auto_explain_on_page_change",
            String(prefs.auto_explain_on_page_change)
          )
        }
      } catch {
        console.log("[StudyReader] Using default auto-explain setting")
      }
    }

    void loadPreference()
  }, [userId])

  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === "auto_explain_on_page_change" && event.newValue !== null) {
        setAutoExplainOnPageChange(event.newValue === "true")
      }
    }

    const handleCustomEvent = (event: CustomEvent<boolean>) => {
      setAutoExplainOnPageChange(event.detail)
    }

    window.addEventListener("storage", handleStorageChange)
    window.addEventListener(
      "autoExplainSettingChanged",
      handleCustomEvent as EventListener
    )

    return () => {
      window.removeEventListener("storage", handleStorageChange)
      window.removeEventListener(
        "autoExplainSettingChanged",
        handleCustomEvent as EventListener
      )
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
    handleQuizComplete,
  } = useChatSession(materialId, userId, pageCount, initialPage, autoExplainOnPageChange)

  const pageSnippets = useMemo(
    () => allSnippets.filter((snippet) => snippet.page_number === currentPage),
    [allSnippets, currentPage]
  )

  const fetchSnippets = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/study/snippets/${materialId}?user_id=${userId}`)
      if (response.ok) {
        const snippets: Snippet[] = await response.json()
        setAllSnippets(snippets)
      }
    } catch (error) {
      console.error("Failed to fetch snippets:", error)
    }
  }, [materialId, userId])

  useEffect(() => {
    void fetchSnippets()
  }, [fetchSnippets])

  const handleSaveSnippet = async (blob: Blob) => {
    if (pageSnippets.length >= MAX_SNIPPETS_PER_PAGE) {
      toast.error(`Maximal ${MAX_SNIPPETS_PER_PAGE} Snippets pro Seite erlaubt`)
      return
    }

    try {
      const formData = new FormData()
      formData.append("file", blob)
      formData.append("course_material_id", materialId)
      formData.append("page_number", currentPage.toString())
      formData.append("user_id", userId)

      const response = await fetch(`${API_URL}/api/study/snippets`, {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }))
        throw new Error(errorData.detail || "Failed to save snippet")
      }

      await fetchSnippets()
      toast.success(`Snippet ${pageSnippets.length + 1} fuer Seite ${currentPage} gespeichert`)
    } catch (error) {
      console.error("Error saving snippet:", error)
      toast.error(error instanceof Error ? error.message : "Fehler beim Speichern des Snippets")
    }
  }

  const handleDeleteSnippet = async (snippetId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/study/snippets/${snippetId}?user_id=${userId}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to delete snippet")
      }

      await fetchSnippets()
      toast.success("Snippet geloescht")
    } catch (error) {
      console.error("Error deleting snippet:", error)
      toast.error("Fehler beim Loeschen des Snippets")
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
      setShowCongratulations(true)
    }
  }

  const pageLabel = `Seite ${currentPage} von ${pageCount}`
  const subtitle = courseName
    ? `${courseName} · Tutor-gestuetzter Lesemodus`
    : "Tutor-gestuetzter Lesemodus"

  return (
    <>
      {showCongratulations ? (
        <CongratulationsScreen
          materialId={materialId}
          materialName={materialName}
          courseId={courseId}
          courseName={courseName}
          userId={userId}
          onClose={() => setShowCongratulations(false)}
        />
      ) : null}
      <div className="app-reader-shell">
        <div className="app-reader-toolbar">
          <div className="min-w-0">
            <p className="app-reader-toolbar__title">{materialName || "Study Reader"}</p>
            <p className="app-reader-toolbar__description">{subtitle}</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="app-subtle-chip">
              <FileText className="h-4 w-4" />
              {pageLabel}
            </span>
            <Button
              variant="outline"
              size="icon-touch"
              onClick={handlePreviousPage}
              disabled={currentPage <= 1}
              aria-label="Vorherige Seite"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant={currentPage === pageCount ? "accent" : "outline"}
              size="icon-touch"
              onClick={handleNextPage}
              disabled={currentPage > pageCount}
              aria-label={
                currentPage === pageCount ? "Abschlussansicht oeffnen" : "Naechste Seite"
              }
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 flex flex-col lg:flex-row pb-4 lg:pb-0">
          <PanelGroup orientation="horizontal" className="h-full min-h-0">
            {/* PDF View Panel */}
            <Panel defaultSize={70} minSize={50}>
              <div className="h-full min-h-0 p-3 lg:p-4 lg:pl-6 bg-zinc-100/50 dark:bg-zinc-950">
                <PdfViewer
                  file={pdfUrl}
                  pageNumber={currentPage}
                  onSaveSnippet={handleSaveSnippet}
                  snippets={pageSnippets}
                  maxSnippets={MAX_SNIPPETS_PER_PAGE}
                  onDeleteSnippet={handleDeleteSnippet}
                />
              </div>
            </Panel>

            <PanelResizeHandle className="w-1 bg-transparent hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors mx-0 hidden lg:block" />

            {/* Chat View Panel */}
            <Panel defaultSize={30} minSize={25}>
              <div className="h-full min-h-0 overflow-hidden bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-800 hidden lg:block shadow-[-10px_0_20px_-10px_rgba(0,0,0,0.05)]">
                <ChatInterface
                  messages={messages}
                  onSend={handleSendMessage}
                  isLoading={isLoading}
                  isStreaming={isStreaming}
                  showTools={showTools}
                  onToggleTools={(enabled) => {
                    setShowTools(enabled)
                    localStorage.setItem("study-reader-show-tools", String(enabled))
                  }}
                  onQuizComplete={handleQuizComplete}
                  submittingQuizId={submittingQuizId}
                />
              </div>
            </Panel>
          </PanelGroup>
        </div>
      </div>
    </>
  )
}
