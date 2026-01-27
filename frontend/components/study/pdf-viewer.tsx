"use client"

import { useState, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { SnippetOverlay } from './snippet-overlay'
import { Button } from '@/components/ui/button'
import { Scissors, Trash2, X, Image } from 'lucide-react'
// CSS imports removed - react-pdf v10+ handles styles internally

// Set up PDF.js worker - use local worker from public folder
if (typeof window !== 'undefined') {
  // Use the worker file from public folder (served by Next.js)
  pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
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
  onDeleteSnippet 
}: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSnipping, setIsSnipping] = useState(false)
  const [showSnippetGallery, setShowSnippetGallery] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages)
    setLoading(false)
    setError(null)
  }

  function onDocumentLoadError(error: Error) {
    setError(error.message)
    setLoading(false)
    onLoadError?.(error)
  }

  function onPageRenderSuccess(page: any) {
    // react-pdf doesn't expose the canvas directly via ref prop on Page component in v9+
    // But we can find it in the DOM or use the canvasRef callback if supported
    // In v9/v10, we can access the canvas element from the rendered page
    const canvas = document.querySelector(`.react-pdf__Page[data-page-number="${pageNumber}"] canvas`) as HTMLCanvasElement
    if (canvas) {
      // Store reference to canvas for cropping
      // We use a mutable ref object to store the element
      (canvasRef as any).current = canvas
    }
  }

  const handleSaveSnippet = async (blob: Blob) => {
    if (onSaveSnippet) {
      await onSaveSnippet(blob)
      setIsSnipping(false)
    }
  }

  const canAddMoreSnippets = snippets.length < maxSnippets

  return (
    <div className="flex flex-col items-center justify-center w-full h-full bg-muted/50 rounded-lg p-4 relative">
      {/* Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        {/* Snippet count badge/button */}
        {snippets.length > 0 && (
          <Button
            size="sm"
            variant="secondary"
            className="shadow-md bg-green-500 text-white hover:bg-green-600"
            onClick={() => setShowSnippetGallery(!showSnippetGallery)}
            title={`${snippets.length} Snippet(s) für diese Seite - Klicken zum Anzeigen`}
          >
            <Image className="h-4 w-4 mr-1" />
            {snippets.length}
          </Button>
        )}
        
        {onSaveSnippet && !isSnipping && (
          <Button
            size="sm"
            variant="secondary"
            className={`shadow-md ${canAddMoreSnippets ? 'bg-white/90 hover:bg-white' : 'bg-gray-300 cursor-not-allowed'}`}
            onClick={() => canAddMoreSnippets && setIsSnipping(true)}
            disabled={!canAddMoreSnippets}
            title={canAddMoreSnippets ? 'Neuen Snippet erstellen' : `Max. ${maxSnippets} Snippets pro Seite`}
          >
            <Scissors className="h-4 w-4 mr-2" />
            Snippet {canAddMoreSnippets ? '' : '(max)'}
          </Button>
        )}
      </div>

      {/* Snippet Gallery Popup */}
      {showSnippetGallery && snippets.length > 0 && (
        <div className="absolute top-16 right-4 z-20 bg-white rounded-lg shadow-xl border p-3 max-w-xs">
          <div className="flex justify-between items-center mb-2">
            <span className="font-medium text-sm">Snippets ({snippets.length}/{maxSnippets})</span>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0"
              onClick={() => setShowSnippetGallery(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-2">
            {snippets.map((snippet, index) => (
              <div 
                key={snippet.id} 
                className="flex items-center justify-between bg-gray-50 rounded p-2"
              >
                <span className="text-sm text-gray-600">
                  Snippet {index + 1}
                  <span className="text-xs text-gray-400 ml-2">
                    {new Date(snippet.created_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </span>
                {onDeleteSnippet && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 w-6 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                    onClick={() => onDeleteSnippet(snippet.id)}
                    title="Snippet löschen"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            ))}
          </div>
          {!canAddMoreSnippets && (
            <p className="text-xs text-gray-500 mt-2">
              Max. {maxSnippets} Snippets erreicht
            </p>
          )}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-full">
          <div className="text-muted-foreground">Loading PDF...</div>
        </div>
      )}
      
      {error && (
        <div className="flex items-center justify-center h-full">
          <div className="text-red-600">Error loading PDF: {error}</div>
        </div>
      )}

      <div className="relative">
        {isSnipping && (
          <SnippetOverlay
            canvasRef={canvasRef}
            onSave={handleSaveSnippet}
            onCancel={() => setIsSnipping(false)}
          />
        )}

        <Document
          file={file}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={
            <div className="flex items-center justify-center h-full">
              <div className="text-muted-foreground">Loading PDF...</div>
            </div>
          }
          className="max-w-full"
        >
          {numPages && (
            <Page
              pageNumber={pageNumber}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="shadow-lg"
              width={Math.min(800, typeof window !== 'undefined' ? window.innerWidth * 0.6 : 800)}
              onRenderSuccess={onPageRenderSuccess}
            />
          )}
        </Document>
      </div>
    </div>
  )
}
