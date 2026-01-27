'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { Upload, Loader2, Plus, Trash2, FileText } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { createClient } from '@/lib/supabase/client'
import { toast } from 'sonner'
import type { Course } from '@/types'
import {
  MultiFileUploadList,
  type FileUploadItem,
} from '@/components/courses/multi-file-upload-list'
import { Progress } from '@/components/ui/progress'
import { calculateProcessingProgress, type ProcessingProgressData } from '@/lib/utils/progress'

interface UploadDialogProps {
  courses: Course[]
}

interface CourseFormData {
  title: string
  description?: string
  exam_date?: string
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const MAX_FILES = 20

export function UploadDialog({ courses }: UploadDialogProps) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'select' | 'create'>('select')
  const [selectedCourseId, setSelectedCourseId] = useState<string>('')
  const [files, setFiles] = useState<FileUploadItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CourseFormData>()

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
    if (!fileItem || !selectedCourseId) return

    const courseId = selectedCourseId
    await uploadSingleFile(fileItem, courseId)
  }

  const handleRemoveAll = () => {
    setFiles([])
    setError(null)
  }

  const createCourse = async (data: CourseFormData) => {
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      throw new Error('User not authenticated')
    }

    const { data: course, error: courseError } = await supabase
      .from('courses')
      .insert({
        user_id: user.id,
        title: data.title,
        description: data.description || null,
        exam_date: data.exam_date || null,
      })
      .select()
      .single()

    if (courseError) {
      throw new Error(`Failed to create course: ${courseError.message}`)
    }

    return course.id
  }

  const uploadSingleFile = async (
    fileItem: FileUploadItem,
    courseId: string
  ): Promise<void> => {
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      throw new Error('User not authenticated')
    }

    // Update status to uploading
    setFiles((prev) =>
      prev.map((f) =>
        f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f
      )
    )

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      
      // Check backend connectivity before upload
      try {
        const healthController = new AbortController()
        const healthTimeout = setTimeout(() => healthController.abort(), 5000) // 5 second timeout
        
        const healthResponse = await fetch(`${apiUrl}/health`, {
          method: 'GET',
          signal: healthController.signal,
        })
        
        clearTimeout(healthTimeout)
      } catch (healthError) {
        throw new Error(`Backend server is not reachable at ${apiUrl}. Please ensure the backend is running.`)
      }
      
      const formData = new FormData()
      formData.append('file', fileItem.file)
      formData.append('user_id', user.id)
      formData.append('course_id', courseId)

      // Simulate progress (since fetch doesn't support progress events natively)
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
                progress: 5,
                materialId: result.course_material_id,
              }
            : f
        )
      )
    } catch (err) {
      let errorMessage = err instanceof Error ? err.message : 'Upload fehlgeschlagen'
      
      // Provide user-friendly error messages for common network issues
      if (err instanceof TypeError && err.message.includes('fetch')) {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        errorMessage = `Verbindung zum Server fehlgeschlagen. Bitte überprüfen Sie, ob der Backend-Server unter ${apiUrl} läuft.`
      }
      
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

  const onSubmit = async (data: CourseFormData) => {
    if (files.length === 0) {
      setError('Bitte wählen Sie mindestens eine Datei aus')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      let courseId = selectedCourseId

      // Create new course if in create mode
      if (mode === 'create') {
        courseId = await createCourse(data)
        setSelectedCourseId(courseId)
      }

      if (!courseId) {
        throw new Error('Kein Kurs ausgewählt')
      }

      // Upload files sequentially in order
      const pendingFiles = files.filter((f) => f.status === 'pending' || f.status === 'error')
      
      for (const fileItem of pendingFiles) {
        try {
          await uploadSingleFile(fileItem, courseId)
          toast.success(`${fileItem.file.name} erfolgreich hochgeladen`)
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Upload fehlgeschlagen'
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
          setOpen(false)
          window.location.reload()
        }, 2000)
      } else {
        toast.warning('Einige Dateien konnten nicht hochgeladen werden')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Ein Fehler ist aufgetreten'
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsUploading(false)
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!isUploading) {
      setOpen(newOpen)
      if (!newOpen) {
        // Reset form when closing
        reset()
        setFiles([])
        setSelectedCourseId('')
        setError(null)
        setMode('select')
        setUploadProgress({})
      }
    } else {
      // Warn user if trying to close during upload
      toast.warning('Upload läuft noch. Bitte warten Sie, bis alle Dateien hochgeladen sind.')
    }
  }

  const getOverallProgress = () => {
    if (files.length === 0) return 0
    const totalProgress = files.reduce((sum, f) => sum + (uploadProgress[f.id] || 0), 0)
    return Math.round(totalProgress / files.length)
  }

  // Poll for progress updates on processing files
  useEffect(() => {
    const processingFiles = files.filter(
      (f) => f.status === 'processing' && f.materialId
    )

    if (processingFiles.length === 0) {
      return
    }

    const pollInterval = setInterval(async () => {
      const supabase = createClient()

      for (const fileItem of processingFiles) {
        if (!fileItem.materialId) continue

        try {
          // Query material with all progress-related fields
          const { data: materialData, error: materialError } = await supabase
            .from('course_materials')
            .select('processing_status, page_count, summary, classification')
            .eq('id', fileItem.materialId)
            .single()

          if (materialError) {
            console.error(`Error polling material ${fileItem.materialId}:`, materialError)
            continue
          }

          if (materialData) {
            // Query completed pages count
            const { count: completedPages, error: pagesError } = await supabase
              .from('page_analyses')
              .select('*', { count: 'exact', head: true })
              .eq('course_material_id', fileItem.materialId)

            if (pagesError) {
              console.error(`Error counting pages for material ${fileItem.materialId}:`, pagesError)
            }

            // Calculate progress
            const progressData: ProcessingProgressData = {
              status: materialData.processing_status as 'uploading' | 'processing' | 'completed' | 'error',
              completedPages: completedPages || 0,
              totalPages: materialData.page_count || 0,
              hasSummary: !!materialData.summary,
              hasClassification: !!materialData.classification,
            }

            const progressResult = calculateProcessingProgress(progressData)

            // Update file with progress
            setFiles((prev) =>
              prev.map((f) =>
                f.id === fileItem.id
                  ? {
                      ...f,
                      status: progressData.status === 'completed' ? 'completed' : f.status,
                      processingProgress: progressResult.progress,
                      processingStage: progressResult.stage,
                      processingStageMessage: progressResult.stageMessage,
                      progress: progressResult.progress,
                    }
                  : f
              )
            )

            // Update upload progress for overall calculation
            setUploadProgress((prev) => ({
              ...prev,
              [fileItem.id]: progressResult.progress,
            }))

            // If completed, stop polling for this file
            if (progressData.status === 'completed' || progressData.status === 'error') {
              // File will be removed from processingFiles on next render
            }
          }
        } catch (error) {
          console.error(`Error polling material ${fileItem.materialId}:`, error)
        }
      }
    }, 2000) // Poll every 2 seconds

    return () => {
      clearInterval(pollInterval)
    }
  }, [files])

  const completedCount = files.filter((f) => f.status === 'completed').length
  const errorCount = files.filter((f) => f.status === 'error').length
  const uploadingCount = files.filter((f) => f.status === 'uploading' || f.status === 'processing').length

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Materialien hochladen
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Materialien hochladen</DialogTitle>
          <DialogDescription>
            Erstellen Sie einen neuen Kurs oder wählen Sie einen bestehenden aus, dann laden Sie PDF-Dateien hoch.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="files" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="files">Dateien auswählen</TabsTrigger>
            <TabsTrigger value="status" disabled={files.length === 0}>
              Upload-Status ({files.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="files" className="space-y-4">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {/* Mode Selection */}
              <div className="space-y-2">
                <Label>Kurs</Label>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant={mode === 'select' ? 'default' : 'outline'}
                    onClick={() => setMode('select')}
                    className="flex-1"
                  >
                    Vorhandenen wählen
                  </Button>
                  <Button
                    type="button"
                    variant={mode === 'create' ? 'default' : 'outline'}
                    onClick={() => setMode('create')}
                    className="flex-1"
                  >
                    Neuen erstellen
                  </Button>
                </div>
              </div>

              {/* Select Existing Course */}
              {mode === 'select' && (
                <div className="space-y-2">
                  <Label htmlFor="course-select">Kurs auswählen</Label>
                  <Select
                    value={selectedCourseId}
                    onValueChange={setSelectedCourseId}
                    required
                  >
                    <SelectTrigger id="course-select">
                      <SelectValue placeholder="Kurs wählen" />
                    </SelectTrigger>
                    <SelectContent>
                      {courses.length === 0 ? (
                        <SelectItem value="" disabled>
                          Keine Kurse verfügbar
                        </SelectItem>
                      ) : (
                        courses.map((course) => (
                          <SelectItem key={course.id} value={course.id}>
                            {course.title}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Create New Course */}
              {mode === 'create' && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Kursname *</Label>
                    <Input
                      id="title"
                      {...register('title', { required: 'Kursname ist erforderlich' })}
                      placeholder="z.B. Marketing 101"
                    />
                    {errors.title && (
                      <p className="text-sm text-red-600">{errors.title.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Beschreibung</Label>
                    <Input
                      id="description"
                      {...register('description')}
                      placeholder="Optionale Kursbeschreibung"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="exam_date">Prüfungsdatum</Label>
                    <Input
                      id="exam_date"
                      type="date"
                      {...register('exam_date')}
                    />
                  </div>
                </div>
              )}

              {/* File Upload */}
              <div className="space-y-2">
                <Label htmlFor="file">PDF-Dateien *</Label>
                <div className="flex items-center gap-2">
                  <Input
                    ref={fileInputRef}
                    id="file"
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={handleFileChange}
                    disabled={isUploading}
                    className="flex-1"
                  />
                  {files.length > 0 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRemoveAll}
                      disabled={isUploading}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Alle entfernen
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Mehrere Dateien auswählen möglich. Max. {MAX_FILES} Dateien, je max. {MAX_FILE_SIZE / 1024 / 1024}MB
                </p>
              </div>

              {/* File List */}
              {files.length > 0 && (
                <div className="space-y-2">
                  <Label>Ausgewählte Dateien ({files.length})</Label>
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

              {/* Error Message */}
              {error && (
                <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
                  {error}
                </div>
              )}

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleOpenChange(false)}
                  disabled={isUploading}
                >
                  Abbrechen
                </Button>
                <Button
                  type="submit"
                  disabled={isUploading || files.length === 0 || !selectedCourseId}
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
              </DialogFooter>
            </form>
          </TabsContent>

          <TabsContent value="status" className="space-y-4">
            <div className="space-y-4">
              {/* Overall Progress */}
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
                  <span>⏳ Wartend: {files.length - completedCount - uploadingCount - errorCount}</span>
                </div>
              </div>

              {/* File List with Status */}
              <div className="max-h-[400px] overflow-y-auto">
                <MultiFileUploadList
                  files={files}
                  onReorder={handleReorderFiles}
                  onRemove={handleRemoveFile}
                  onRetry={handleRetryUpload}
                  disabled={isUploading}
                />
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
