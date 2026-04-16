"use client"

import { useRef, useState } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import { Image, Scissors, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { SnippetOverlay } from "./snippet-overlay"

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"
}

interface Snippet {
  id: string
  page_number: number
  image_path: string
  created_at: string
  order_index?: number
}

interface PdfViewerProps {
  file: string | File
  pageNumber: number
  onLoadError?: (error: Error) => void
  onSaveSnippet?: (blob: Blob) => Promise<void>
  snippets?: Snippet[]
  maxSnippets?: number
  onDeleteSnippet?: (snippetId: string) => Promise<void>
}

export function PdfViewer({
  file,
  pageNumber,
  onLoadError,
  onSaveSnippet,
  snippets = [],
  maxSnippets = 3,
  onDeleteSnippet,
}: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSnipping, setIsSnipping] = useState(false)
  const [showSnippetGallery, setShowSnippetGallery] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const pageContainerRef = useRef<HTMLDivElement | null>(null)

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages)
    setLoading(false)
    setError(null)
  }

  function onDocumentLoadError(nextError: Error) {
    setError(nextError.message)
    setLoading(false)
    onLoadError?.(nextError)
  }

  function onPageRenderSuccess() {
    const canvas = pageContainerRef.current?.querySelector("canvas")
    if (canvas instanceof HTMLCanvasElement) {
      canvasRef.current = canvas
    }
  }

  const handleSaveSnippet = async (blob: Blob) => {
    if (!onSaveSnippet) {
      return
    }

    await onSaveSnippet(blob)
    setIsSnipping(false)
  }

  const canAddMoreSnippets = snippets.length < maxSnippets

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden rounded-[1.5rem] border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)]">
      <div className="flex items-center justify-end gap-2 border-b border-[var(--app-border-soft)] px-4 py-3">
        {snippets.length > 0 ? (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowSnippetGallery((current) => !current)}
            aria-label="Snippet-Galerie umschalten"
          >
            <Image className="h-4 w-4" />
            {snippets.length}
          </Button>
        ) : null}

        {onSaveSnippet && !isSnipping ? (
          <Button
            size="sm"
            variant="ghost"
            className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-200 dark:hover:bg-zinc-800"
            onClick={() => canAddMoreSnippets && setIsSnipping(true)}
            disabled={!canAddMoreSnippets}
            aria-label={
              canAddMoreSnippets
                ? "Neuen Snippet erstellen"
                : `Maximal ${maxSnippets} Snippets erreicht`
            }
          >
            <Scissors className="h-4 w-4" />
            {canAddMoreSnippets ? "Snippet erstellen" : "Limit erreicht"}
          </Button>
        ) : null}
      </div>

      {showSnippetGallery && snippets.length > 0 ? (
        <div className="absolute right-4 top-16 z-20 w-full max-w-xs rounded-[1.25rem] border border-[var(--app-border-soft)] bg-[var(--app-surface)] p-3 shadow-[var(--app-shadow-panel)]">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Snippets ({snippets.length}/{maxSnippets})
            </span>
            <Button
              size="icon-touch"
              variant="ghost"
              className="h-9 w-9"
              onClick={() => setShowSnippetGallery(false)}
              aria-label="Snippet-Galerie schliessen"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-2">
            {snippets.map((snippet, index) => (
              <div
                key={snippet.id}
                className="flex items-center justify-between rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] p-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">Snippet {index + 1}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(snippet.created_at).toLocaleTimeString("de-DE", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                {onDeleteSnippet ? (
                  <Button
                    size="icon-touch"
                    variant="ghost"
                    className="h-9 w-9 text-red-500 hover:bg-red-50 hover:text-red-700"
                    onClick={() => void onDeleteSnippet(snippet.id)}
                    aria-label={`Snippet ${index + 1} loeschen`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
          {!canAddMoreSnippets ? (
            <p className="mt-3 text-xs text-muted-foreground">Maximal {maxSnippets} Snippets pro Seite erreicht</p>
          ) : null}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-muted-foreground">
            Loading PDF...
          </div>
        ) : null}

        {error ? (
          <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-red-600">
            Error loading PDF: {error}
          </div>
        ) : null}

        <div ref={pageContainerRef} className="relative flex min-h-full items-start justify-center">
          {isSnipping ? (
            <SnippetOverlay
              canvasRef={canvasRef}
              onSave={handleSaveSnippet}
              onCancel={() => setIsSnipping(false)}
            />
          ) : null}

          <Document
            file={file}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-zinc-500">
                Loading PDF...
              </div>
            }
            className="max-w-full drop-shadow-xl"
          >
            {numPages ? (
              <Page
                pageNumber={pageNumber}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className="overflow-hidden rounded-md border border-zinc-200/50 dark:border-zinc-800/50 bg-white"
                width={Math.min(900, typeof window !== "undefined" ? window.innerWidth * 0.65 : 900)}
                onRenderSuccess={onPageRenderSuccess}
              />
            ) : null}
          </Document>
        </div>
      </div>
    </div>
  )
}
