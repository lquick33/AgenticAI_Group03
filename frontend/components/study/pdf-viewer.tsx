"use client"

import { useState, useRef } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { SnippetOverlay } from './snippet-overlay'
import { Button } from '@/components/ui/button'
import { Scissors } from 'lucide-react'
// CSS imports removed - react-pdf v10+ handles styles internally

// Set up PDF.js worker - use local worker from public folder
if (typeof window !== 'undefined') {
  // Use the worker file from public folder (served by Next.js)
  pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
}

interface PdfViewerProps {
  file: string | File
  pageNumber: number
  onLoadError?: (error: Error) => void
  onSaveSnippet?: (blob: Blob) => Promise<void>
  hasSnippet?: boolean
}

export function PdfViewer({ file, pageNumber, onLoadError, onSaveSnippet, hasSnippet }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSnipping, setIsSnipping] = useState(false)
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

  return (
    <div className="flex flex-col items-center justify-center w-full h-full bg-muted/50 rounded-lg p-4 relative">
      {/* Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        {hasSnippet && (
          <div className="bg-green-500 text-white p-2 rounded-full shadow-md" title="Snippet saved for this page">
            <Scissors className="h-4 w-4" />
          </div>
        )}
        
        {onSaveSnippet && !isSnipping && (
          <Button
            size="sm"
            variant="secondary"
            className="shadow-md bg-white/90 hover:bg-white"
            onClick={() => setIsSnipping(true)}
            title="Create image snippet"
          >
            <Scissors className="h-4 w-4 mr-2" />
            Snippet
          </Button>
        )}
      </div>

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
