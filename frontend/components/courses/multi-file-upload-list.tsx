"use client"

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { AlertCircle, CheckCircle2, GripVertical, Loader2, Upload, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

export interface FileUploadItem {
  id: string
  file: File
  status: "pending" | "uploading" | "processing" | "completed" | "error"
  progress?: number
  processingProgress?: number
  processingStage?: string
  processingStageMessage?: string
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
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) {
      return "0 Bytes"
    }

    const kiloByte = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const index = Math.floor(Math.log(bytes) / Math.log(kiloByte))
    return `${Math.round((bytes / Math.pow(kiloByte, index)) * 100) / 100} ${sizes[index]}`
  }

  const getStatusBadge = () => {
    switch (item.status) {
      case "pending":
        return <Badge variant="outline" className="text-xs">Wartend</Badge>
      case "uploading":
        return <Badge variant="default" className="bg-blue-500 text-xs">Wird hochgeladen...</Badge>
      case "processing":
        return <Badge variant="default" className="bg-yellow-500 text-xs">Wird verarbeitet...</Badge>
      case "completed":
        return <Badge variant="default" className="bg-green-500 text-xs">Fertig</Badge>
      case "error":
        return <Badge variant="destructive" className="text-xs">Fehler</Badge>
    }
  }

  const getStatusIcon = () => {
    switch (item.status) {
      case "pending":
        return <Upload className="h-4 w-4 text-muted-foreground" />
      case "uploading":
      case "processing":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-3 rounded-lg border bg-card p-3",
        isDragging && "opacity-50 shadow-lg",
        item.status === "error" && "border-red-200 bg-red-50/50"
      )}
    >
      <div
        {...attributes}
        {...listeners}
        className={cn(
          "cursor-grab text-muted-foreground transition-colors hover:text-foreground active:cursor-grabbing",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <GripVertical className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          {getStatusIcon()}
          <span className="truncate text-sm font-medium">{item.file.name}</span>
          {getStatusBadge()}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatFileSize(item.file.size)}</span>
          {item.status === "error" && item.errorMessage && (
            <span className="truncate text-red-600">{item.errorMessage}</span>
          )}
        </div>
        {(item.status === "uploading" || item.status === "processing") && (
          <div className="mt-2 space-y-1">
            <Progress
              value={
                item.processingProgress !== undefined ? item.processingProgress : item.progress || 0
              }
              className="h-1.5"
            />
            {item.processingProgress !== undefined && (
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{item.processingProgress}%</span>
                {item.processingStageMessage && (
                  <span className="ml-2 truncate">{item.processingStageMessage}</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        {item.status === "error" && onRetry && (
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
          disabled={disabled || item.status === "uploading"}
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          aria-label={`${item.file.name} entfernen`}
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
      const oldIndex = files.findIndex((file) => file.id === active.id)
      const newIndex = files.findIndex((file) => file.id === over.id)
      const reorderedFiles = arrayMove(files, oldIndex, newIndex).map((file, index) => ({
        ...file,
        order: index + 1,
      }))
      onReorder(reorderedFiles)
    }
  }

  if (files.length === 0) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Keine Dateien ausgewaehlt</div>
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={files.map((file) => file.id)} strategy={verticalListSortingStrategy}>
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
