"use client"

import { useState, useRef } from 'react'
import { Upload, Loader2, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Label } from '@/components/ui/label'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { createClient } from '@/lib/supabase/client'
import {
  MultiFileUploadList,
  type FileUploadItem,
} from '@/components/courses/multi-file-upload-list'

interface UploadSectionProps {
  courseId: string
  userId: string
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const MAX_FILES = 20

export function UploadSection({ courseId, userId }: UploadSectionProps) {
  const [files, setFiles] = useState<FileUploadItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const supabase = createClient()

  const validateFile = (file: File): string | null => {
    if (file.type !== 'application/pdf') {
      return 'Nur PDF-Dateien sind erlaubt'
    }
    if (file.size > MAX_FILE_SIZE) {
      return `Datei ist zu groß (max. ${MAX_FILE_SIZE / 1024 / 1024}MB)`
    }
    return null
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || [])
    
    if (selectedFiles.length === 0) return

    // Check total file count
    if (files.length + selectedFiles.length > MAX_FILES) {
      setError(`Maximal ${MAX_FILES} Dateien gleichzeitig`)
      toast.error(`Maximal ${MAX_FILES} Dateien gleichzeitig`)
      return
    }

    const newFiles: FileUploadItem[] = []
    const errors: string[] = []

    selectedFiles.forEach((file) => {
      const validationError = validateFile(file)
      if (validationError) {
        errors.push(`${file.name}: ${validationError}`)
        return
      }

      // Check for duplicates
      if (files.some((f) => f.file.name === file.name && f.file.size === file.size)) {
        errors.push(`${file.name}: Datei bereits hinzugefügt`)
        return
      }

      newFiles.push({
        id: `${Date.now()}-${Math.random()}`,
        file,
        status: 'pending',
        order: files.length + newFiles.length + 1,
      })
    })

    if (errors.length > 0) {
      setError(errors.join(', '))
      toast.error('Einige Dateien konnten nicht hinzugefügt werden', {
        description: errors.slice(0, 3).join('; '),
      })
    }

    if (newFiles.length > 0) {
      setFiles((prev) => [...prev, ...newFiles])
      setError(null)
      toast.success(`${newFiles.length} Datei${newFiles.length > 1 ? 'en' : ''} hinzugefügt`)
    }

    // Reset input to allow selecting same file again
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleRemoveFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const handleReorderFiles = (reorderedFiles: FileUploadItem[]) => {
    setFiles(reorderedFiles)
  }

  const handleRetryUpload = async (id: string) => {
    const fileItem = files.find((f) => f.id === id)
    if (!fileItem) return
    await uploadSingleFile(fileItem)
  }

  const handleRemoveAll = () => {
    setFiles([])
    setError(null)
  }

  const uploadSingleFile = async (fileItem: FileUploadItem): Promise<void> => {
    // Update status to uploading
    setFiles((prev) =>
      prev.map((f) =>
        f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f
      )
    )

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const formData = new FormData()
      formData.append('file', fileItem.file)
      formData.append('user_id', userId)
      formData.append('course_id', courseId)

      // Simulate progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => ({
          ...prev,
          [fileItem.id]: Math.min((prev[fileItem.id] || 0) + 10, 90),
        }))
      }, 200)

      const response = await fetch(`${apiUrl}/api/upload`, {
        method: 'POST',
        body: formData,
      })

      clearInterval(progressInterval)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: 'Upload failed',
        }))
        throw new Error(errorData.detail || `Upload failed: ${response.statusText}`)
      }

      const result = await response.json()

      // Update to processing
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileItem.id
            ? {
                ...f,
                status: 'processing',
                progress: 95,
                materialId: result.course_material_id,
              }
            : f
        )
      )

      // Simulate processing progress
      const processingInterval = setInterval(() => {
        setUploadProgress((prev) => ({
          ...prev,
          [fileItem.id]: Math.min((prev[fileItem.id] || 95) + 1, 99),
        }))
      }, 500)

      // Poll for completion
      setTimeout(() => {
        clearInterval(processingInterval)
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileItem.id
              ? { ...f, status: 'completed', progress: 100 }
              : f
          )
        )
        setUploadProgress((prev) => ({
          ...prev,
          [fileItem.id]: 100,
        }))
      }, 2000)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Upload fehlgeschlagen'
      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileItem.id
            ? { ...f, status: 'error', errorMessage }
            : f
        )
      )
      throw err
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Bitte wählen Sie mindestens eine Datei aus')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      // Upload files sequentially in order
      const pendingFiles = files.filter(
        (f) => f.status === 'pending' || f.status === 'error'
      )

      for (const fileItem of pendingFiles) {
        try {
          await uploadSingleFile(fileItem)
          toast.success(`${fileItem.file.name} erfolgreich hochgeladen`)
        } catch (err) {
          const errorMessage =
            err instanceof Error ? err.message : 'Upload fehlgeschlagen'
          toast.error(`Fehler bei ${fileItem.file.name}`, {
            description: errorMessage,
          })
        }
      }

      // Check if all files are completed
      const allCompleted = files.every(
        (f) => f.status === 'completed' || f.status === 'processing'
      )

      if (allCompleted) {
        toast.success('Alle Dateien erfolgreich hochgeladen!')
        setTimeout(() => {
          router.refresh()
        }, 2000)
      } else {
        toast.warning('Einige Dateien konnten nicht hochgeladen werden')
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Ein Fehler ist aufgetreten'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsUploading(false)
    }
  }

  const getOverallProgress = () => {
    if (files.length === 0) return 0
    const totalProgress = files.reduce(
      (sum, f) => sum + (uploadProgress[f.id] || 0),
      0
    )
    return Math.round(totalProgress / files.length)
  }

  const completedCount = files.filter((f) => f.status === 'completed').length
  const errorCount = files.filter((f) => f.status === 'error').length
  const uploadingCount = files.filter(
    (f) => f.status === 'uploading' || f.status === 'processing'
  ).length

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Vorlesungsmaterial hochladen</h3>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-800 mb-4">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-4">
          {/* File Upload Area */}
          <div>
            <label
              htmlFor="file-upload"
              className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-muted-foreground/25 rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
                <p className="mb-2 text-sm text-muted-foreground">
                  <span className="font-semibold">Klicke zum Hochladen</span> oder
                  ziehe die Dateien hierher
                </p>
                <p className="text-xs text-muted-foreground">
                  PDF (max. {MAX_FILE_SIZE / 1024 / 1024}MB, max. {MAX_FILES} Dateien)
                </p>
              </div>
              <input
                ref={fileInputRef}
                id="file-upload"
                type="file"
                className="hidden"
                accept=".pdf"
                multiple
                onChange={handleFileChange}
                disabled={isUploading}
              />
            </label>
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Ausgewählte Dateien ({files.length})</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRemoveAll}
                  disabled={isUploading}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Alle entfernen
                </Button>
              </div>
              <div className="max-h-[300px] overflow-y-auto">
                <MultiFileUploadList
                  files={files}
                  onReorder={handleReorderFiles}
                  onRemove={handleRemoveFile}
                  onRetry={handleRetryUpload}
                  disabled={isUploading}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                💡 Ziehen Sie die Dateien, um die Upload-Reihenfolge zu ändern
              </p>
            </div>
          )}

          {/* Overall Progress */}
          {isUploading && files.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Gesamtfortschritt</span>
                <span className="text-muted-foreground">
                  {completedCount} von {files.length} Dateien fertig
                </span>
              </div>
              <Progress value={getOverallProgress()} className="h-2" />
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>✅ Fertig: {completedCount}</span>
                <span>🔄 Läuft: {uploadingCount}</span>
                <span>❌ Fehler: {errorCount}</span>
                <span>
                  ⏳ Wartend:{' '}
                  {files.length - completedCount - uploadingCount - errorCount}
                </span>
              </div>
            </div>
          )}

          <Button
            onClick={handleUpload}
            disabled={files.length === 0 || isUploading}
            className="w-full"
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Wird hochgeladen...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                {files.length > 0
                  ? `${files.length} Datei${files.length > 1 ? 'en' : ''} hochladen`
                  : 'Hochladen'}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
