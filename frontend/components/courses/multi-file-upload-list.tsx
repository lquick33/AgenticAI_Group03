"use client"

import { useState } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, X, AlertCircle, CheckCircle2, Loader2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export interface FileUploadItem {
  id: string
  file: File
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error'
  progress?: number
  errorMessage?: string
  materialId?: string
  order: number
}

interface MultiFileUploadListProps {
  files: FileUploadItem[]
  onReorder: (files: FileUploadItem[]) => void
  onRemove: (id: string) => void
  onRetry?: (id: string) => void
  disabled?: boolean
}

function SortableFileItem({
  item,
  onRemove,
  onRetry,
  disabled,
}: {
  item: FileUploadItem
  onRemove: (id: string) => void
  onRetry?: (id: string) => void
  disabled?: boolean
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getStatusBadge = () => {
    switch (item.status) {
      case 'pending':
        return (
          <Badge variant="outline" className="text-xs">
            Wartend
          </Badge>
        )
      case 'uploading':
        return (
          <Badge variant="default" className="text-xs bg-blue-500">
            Wird hochgeladen...
          </Badge>
        )
      case 'processing':
        return (
          <Badge variant="default" className="text-xs bg-yellow-500">
            Wird verarbeitet...
          </Badge>
        )
      case 'completed':
        return (
          <Badge variant="default" className="text-xs bg-green-500">
            Fertig
          </Badge>
        )
      case 'error':
        return (
          <Badge variant="destructive" className="text-xs">
            Fehler
          </Badge>
        )
    }
  }

  const getStatusIcon = () => {
    switch (item.status) {
      case 'pending':
        return <Upload className="h-4 w-4 text-muted-foreground" />
      case 'uploading':
      case 'processing':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border bg-card',
        isDragging && 'opacity-50 shadow-lg',
        item.status === 'error' && 'border-red-200 bg-red-50/50'
      )}
    >
      {/* Drag Handle */}
      <div
        {...attributes}
        {...listeners}
        className={cn(
          'cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground transition-colors',
          disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <GripVertical className="h-5 w-5" />
      </div>

      {/* File Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          {getStatusIcon()}
          <span className="text-sm font-medium truncate">{item.file.name}</span>
          {getStatusBadge()}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatFileSize(item.file.size)}</span>
          {item.status === 'error' && item.errorMessage && (
            <span className="text-red-600 truncate">{item.errorMessage}</span>
          )}
        </div>
        {/* Progress Bar */}
        {(item.status === 'uploading' || item.status === 'processing') && (
          <div className="mt-2">
            <Progress
              value={item.progress || 0}
              className="h-1.5"
            />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {item.status === 'error' && onRetry && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRetry(item.id)}
            disabled={disabled}
            className="h-8 px-2"
          >
            Erneut versuchen
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onRemove(item.id)}
          disabled={disabled || item.status === 'uploading'}
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export function MultiFileUploadList({
  files,
  onReorder,
  onRemove,
  onRetry,
  disabled = false,
}: MultiFileUploadListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const oldIndex = files.findIndex((f) => f.id === active.id)
      const newIndex = files.findIndex((f) => f.id === over.id)

      const newFiles = arrayMove(files, oldIndex, newIndex)
      // Update order numbers
      const reorderedFiles = newFiles.map((file, index) => ({
        ...file,
        order: index + 1,
      }))
      onReorder(reorderedFiles)
    }
  }

  if (files.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        Keine Dateien ausgewählt
      </div>
    )
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={files.map((f) => f.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-2">
          {files.map((file) => (
            <SortableFileItem
              key={file.id}
              item={file}
              onRemove={onRemove}
              onRetry={onRetry}
              disabled={disabled}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  )
}
