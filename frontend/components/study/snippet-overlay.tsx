"use client"

import { useRef, useState } from "react"
import { Check, X } from "lucide-react"

import { Button } from "@/components/ui/button"

interface SnippetOverlayProps {
  onSave: (blob: Blob) => Promise<void>
  onCancel: () => void
  canvasRef: React.RefObject<HTMLCanvasElement | null>
}

export function SnippetOverlay({ onSave, onCancel, canvasRef }: SnippetOverlayProps) {
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null)
  const [currentPos, setCurrentPos] = useState<{ x: number; y: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  const handleMouseDown = (event: React.MouseEvent) => {
    if (!overlayRef.current || isSaving) {
      return
    }

    if ((event.target as HTMLElement).closest("button")) {
      return
    }

    if (startPos && currentPos && !isDragging) {
      setStartPos(null)
      setCurrentPos(null)
    }

    const rect = overlayRef.current.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    setStartPos({ x, y })
    setCurrentPos({ x, y })
    setIsDragging(true)
  }

  const handleMouseMove = (event: React.MouseEvent) => {
    if (!startPos || !overlayRef.current || !isDragging) {
      return
    }

    const rect = overlayRef.current.getBoundingClientRect()
    setCurrentPos({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    })
  }

  const handleMouseUp = () => {
    if (isDragging) {
      setIsDragging(false)
    }
  }

  const handleSave = async () => {
    if (!startPos || !currentPos || !canvasRef.current || !overlayRef.current) {
      return
    }

    setIsSaving(true)

    try {
      const x = Math.min(startPos.x, currentPos.x)
      const y = Math.min(startPos.y, currentPos.y)
      const width = Math.abs(currentPos.x - startPos.x)
      const height = Math.abs(currentPos.y - startPos.y)

      if (width < 10 || height < 10) {
        return
      }

      const sourceCanvas = canvasRef.current
      const rect = overlayRef.current.getBoundingClientRect()
      const scaleX = sourceCanvas.width / rect.width
      const scaleY = sourceCanvas.height / rect.height

      const tempCanvas = document.createElement("canvas")
      tempCanvas.width = width * scaleX
      tempCanvas.height = height * scaleY
      const context = tempCanvas.getContext("2d")

      if (!context) {
        throw new Error("Could not get canvas context")
      }

      context.drawImage(
        sourceCanvas,
        x * scaleX,
        y * scaleY,
        width * scaleX,
        height * scaleY,
        0,
        0,
        tempCanvas.width,
        tempCanvas.height
      )

      const blob = await new Promise<Blob>((resolve, reject) => {
        tempCanvas.toBlob((result) => {
          if (result) {
            resolve(result)
            return
          }

          reject(new Error("Failed to create blob"))
        }, "image/png")
      })

      await onSave(blob)
    } catch (error) {
      console.error("Failed to save snippet:", error)
    } finally {
      setIsSaving(false)
    }
  }

  const getSelectionStyle = () => {
    if (!startPos || !currentPos) {
      return {}
    }

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
      {startPos && currentPos && (
        <div className="absolute border-2 border-primary bg-white/10 backdrop-blur-[1px]" style={getSelectionStyle()}>
          <div className="absolute -bottom-14 right-0 flex gap-2">
            <Button
              size="icon-touch"
              variant="secondary"
              onClick={(event) => {
                event.stopPropagation()
                onCancel()
              }}
              disabled={isSaving}
              aria-label="Snippet-Auswahl verwerfen"
            >
              <X className="h-4 w-4" />
            </Button>
            <Button
              size="icon-touch"
              variant="accent"
              onClick={(event) => {
                event.stopPropagation()
                void handleSave()
              }}
              disabled={isSaving}
              aria-label="Snippet speichern"
            >
              <Check className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {!startPos && (
        <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-black/75 px-4 py-2 text-sm text-white">
          Click and drag to select an area
        </div>
      )}
    </div>
  )
}
