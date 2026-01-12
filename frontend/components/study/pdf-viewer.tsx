"use client"

import { useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
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
}

export function PdfViewer({ file, pageNumber, onLoadError }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="flex flex-col items-center justify-center w-full h-full bg-muted/50 rounded-lg p-4">
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
          />
        )}
      </Document>
    </div>
  )
}
