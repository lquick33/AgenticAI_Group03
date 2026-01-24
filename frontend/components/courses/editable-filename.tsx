"use client"

import { useState, useRef, useEffect } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { updateMaterialFilename } from '@/lib/api/materials'
import { toast } from 'sonner'

interface EditableFilenameProps {
  materialId: string
  userId: string
  initialFilename: string
  onUpdate?: (newFilename: string) => void
}

export function EditableFilename({
  materialId,
  userId,
  initialFilename,
  onUpdate,
}: EditableFilenameProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [filename, setFilename] = useState(initialFilename)
  const [isSaving, setIsSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Update local state when initialFilename changes from parent
  useEffect(() => {
    if (!isEditing) {
      setFilename(initialFilename)
    }
  }, [initialFilename, isEditing])

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      // Select all text for easy replacement
      inputRef.current.select()
    }
  }, [isEditing])

  const handleDoubleClick = () => {
    setIsEditing(true)
  }

  const handleSave = async () => {
    const trimmedFilename = filename.trim()
    
    if (!trimmedFilename) {
      toast.error('Fehler', {
        description: 'Der Dateiname darf nicht leer sein.',
      })
      return
    }

    if (trimmedFilename === initialFilename) {
      // No change, just exit edit mode
      setIsEditing(false)
      return
    }

    setIsSaving(true)
    try {
      await updateMaterialFilename(materialId, trimmedFilename, userId)
      setIsEditing(false)
      onUpdate?.(trimmedFilename)
      toast.success('Gespeichert', {
        description: 'Der Dateiname wurde erfolgreich aktualisiert.',
      })
    } catch (error) {
      console.error('Error updating filename:', error)
      toast.error('Fehler beim Speichern', {
        description: error instanceof Error ? error.message : 'Der Dateiname konnte nicht aktualisiert werden.',
      })
      // Revert to original filename on error
      setFilename(initialFilename)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setFilename(initialFilename)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSave()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
    }
  }

  if (isEditing) {
    return (
      <div className="flex items-center gap-1 group">
        <input
          ref={inputRef}
          type="text"
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          disabled={isSaving}
          className="flex-1 bg-transparent border-none outline-none focus:outline-none font-medium text-foreground min-w-0 px-0"
          style={{ caretColor: 'currentColor' }}
        />
        {isSaving ? (
          <Loader2 className="h-3 w-3 text-muted-foreground animate-spin flex-shrink-0" />
        ) : (
          <button
            onClick={handleSave}
            className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 p-0.5 hover:bg-muted rounded"
            aria-label="Speichern"
          >
            <Check className="h-3 w-3 text-green-600" />
          </button>
        )}
      </div>
    )
  }

  return (
    <span
      onDoubleClick={handleDoubleClick}
      className="font-medium cursor-pointer hover:text-primary transition-colors select-none"
      title="Doppelklick zum Bearbeiten"
    >
      {filename}
    </span>
  )
}
