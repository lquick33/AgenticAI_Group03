"use client"

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { X, Check } from 'lucide-react'

interface SnippetOverlayProps {
  onSave: (blob: Blob) => Promise<void>
  onCancel: () => void
  canvasRef: React.RefObject<HTMLCanvasElement>
}

export function SnippetOverlay({ onSave, onCancel, canvasRef }: SnippetOverlayProps) {
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null)
  const [currentPos, setCurrentPos] = useState<{ x: number; y: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Handle mouse events for selection
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!overlayRef.current || isSaving) return
    
    // Only start new selection if clicking on background (not on buttons)
    if ((e.target as HTMLElement).closest('button')) return

    // If we already have a selection and click outside it, reset
    if (startPos && currentPos && !isDragging) {
      setStartPos(null)
      setCurrentPos(null)
    }

    const rect = overlayRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setStartPos({ x, y })
    setCurrentPos({ x, y })
    setIsDragging(true)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!startPos || !overlayRef.current || !isDragging) return
    const rect = overlayRef.current.getBoundingClientRect()
    setCurrentPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    })
  }

  const handleMouseUp = () => {
    if (isDragging) {
      setIsDragging(false)
    }
  }

  const handleSave = async () => {
    if (!startPos || !currentPos || !canvasRef.current) return
    setIsSaving(true)

    try {
      // Calculate selection coordinates relative to the overlay
      const x = Math.min(startPos.x, currentPos.x)
      const y = Math.min(startPos.y, currentPos.y)
      const width = Math.abs(currentPos.x - startPos.x)
      const height = Math.abs(currentPos.y - startPos.y)

      if (width < 10 || height < 10) return // Ignore tiny selections

      // Get the source canvas
      const sourceCanvas = canvasRef.current
      
      // Calculate scaling factor between overlay and actual canvas resolution
      // The overlay matches the CSS size of the canvas, but the canvas internal resolution might be higher (DPI)
      const rect = overlayRef.current!.getBoundingClientRect()
      const scaleX = sourceCanvas.width / rect.width
      const scaleY = sourceCanvas.height / rect.height

      // Create a temporary canvas for the cropped image
      const tempCanvas = document.createElement('canvas')
      tempCanvas.width = width * scaleX
      tempCanvas.height = height * scaleY
      const ctx = tempCanvas.getContext('2d')

      if (!ctx) throw new Error('Could not get canvas context')

      // Draw the cropped portion
      ctx.drawImage(
        sourceCanvas,
        x * scaleX, y * scaleY, width * scaleX, height * scaleY, // Source rect
        0, 0, tempCanvas.width, tempCanvas.height // Dest rect
      )

      // Convert to blob
      const blob = await new Promise<Blob>((resolve, reject) => {
        tempCanvas.toBlob((b) => {
          if (b) resolve(b)
          else reject(new Error('Failed to create blob'))
        }, 'image/png')
      })

      await onSave(blob)
    } catch (error) {
      console.error('Failed to save snippet:', error)
    } finally {
      setIsSaving(false)
    }
  }

  // Calculate selection rectangle style
  const getSelectionStyle = () => {
    if (!startPos || !currentPos) return {}
    const left = Math.min(startPos.x, currentPos.x)
    const top = Math.min(startPos.y, currentPos.y)
    const width = Math.abs(currentPos.x - startPos.x)
    const height = Math.abs(currentPos.y - startPos.y)
    return { left, top, width, height }
  }

  return (
    <div 
      ref={overlayRef}
      className="absolute inset-0 z-50 cursor-crosshair bg-black/30"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Selection Box */}
      {startPos && currentPos && (
        <div 
          className="absolute border-2 border-primary bg-white/10 backdrop-blur-[1px]"
          style={getSelectionStyle()}
        >
          {/* Action Buttons attached to selection */}
          <div className="absolute -bottom-12 right-0 flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={(e) => { e.stopPropagation(); onCancel(); }}
              disabled={isSaving}
            >
              <X className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              onClick={(e) => { e.stopPropagation(); handleSave(); }}
              disabled={isSaving}
            >
              <Check className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
      
      {/* Instructions */}
      {!startPos && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-black/75 text-white px-4 py-2 rounded-full text-sm pointer-events-none">
          Click and drag to select an area
        </div>
      )}
    </div>
  )
}
