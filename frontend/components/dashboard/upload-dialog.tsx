"use client"

import { useEffect, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { FileText, Loader2, Plus, Trash2, Upload } from "lucide-react"
import { toast } from "sonner"

import {
  MultiFileUploadList,
  type FileUploadItem,
} from "@/components/courses/multi-file-upload-list"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useBackgroundTasksOptional } from "@/components/background-tasks"
import type { Course } from "@/types"
import { getApiUrl } from "@/lib/public-env"
import { createClient } from "@/lib/supabase/client"
import { mergeFilesWithPdfTasks } from "@/lib/upload-task-utils"

interface UploadDialogProps {
  courses: Course[]
}

interface CourseFormData {
  title: string
  description?: string
  exam_date?: string
}

const MAX_FILE_SIZE = 50 * 1024 * 1024
const MAX_FILES = 20

export function UploadDialog({ courses }: UploadDialogProps) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"select" | "create">("select")
  const [selectedCourseId, setSelectedCourseId] = useState("")
  const [files, setFiles] = useState<FileUploadItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const backgroundTasks = useBackgroundTasksOptional()
  const supabase = createClient()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CourseFormData>()

  useEffect(() => {
    if (!backgroundTasks) {
      return
    }

    const mergedFiles = mergeFilesWithPdfTasks(files, backgroundTasks.tasks)
    setFiles(mergedFiles)
  }, [backgroundTasks?.tasks])

  const validateFile = (file: File): string | null => {
    if (file.type !== "application/pdf") {
      return "Nur PDF-Dateien sind erlaubt"
    }
    if (file.size > MAX_FILE_SIZE) {
      return `Datei ist zu gross (max. ${MAX_FILE_SIZE / 1024 / 1024}MB)`
    }
    return null
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || [])
    if (selectedFiles.length === 0) {
      return
    }

    if (files.length + selectedFiles.length > MAX_FILES) {
      setError(`Maximal ${MAX_FILES} Dateien gleichzeitig`)
      return
    }

    const newFiles: FileUploadItem[] = []
    const nextErrors: string[] = []

    selectedFiles.forEach((file) => {
      const validationError = validateFile(file)
      if (validationError) {
        nextErrors.push(`${file.name}: ${validationError}`)
        return
      }

      if (files.some((candidate) => candidate.file.name === file.name && candidate.file.size === file.size)) {
        nextErrors.push(`${file.name}: Datei bereits hinzugefuegt`)
        return
      }

      newFiles.push({
        id: `${Date.now()}-${Math.random()}`,
        file,
        status: "pending",
        order: files.length + newFiles.length + 1,
      })
    })

    if (nextErrors.length > 0) {
      setError(nextErrors.join(", "))
      toast.error("Einige Dateien konnten nicht hinzugefuegt werden", {
        description: nextErrors.slice(0, 3).join("; "),
      })
    }

    if (newFiles.length > 0) {
      setFiles((prev) => [...prev, ...newFiles])
      setError(null)
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleRemoveFile = (id: string) => {
    setFiles((prev) => prev.filter((file) => file.id !== id))
  }

  const handleReorderFiles = (reorderedFiles: FileUploadItem[]) => {
    setFiles(reorderedFiles)
  }

  const handleRetryUpload = async (id: string) => {
    const fileItem = files.find((file) => file.id === id)
    if (!fileItem || !selectedCourseId) {
      return
    }

    await uploadSingleFile(fileItem, selectedCourseId)
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
      throw new Error("User not authenticated")
    }

    const { data: course, error: courseError } = await supabase
      .from("courses")
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

  const uploadSingleFile = async (fileItem: FileUploadItem, courseId: string): Promise<void> => {
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      throw new Error("User not authenticated")
    }

    const tempTaskId = `upload-${fileItem.id}`
    const selectedCourse = courses.find((course) => course.id === courseId)
    const apiUrl = getApiUrl()

    setFiles((prev) =>
      prev.map((file) =>
        file.id === fileItem.id ? { ...file, status: "uploading", progress: 0 } : file
      )
    )

    backgroundTasks?.addTask({
      id: tempTaskId,
      type: "pdf_processing",
      materialId: tempTaskId,
      materialName: fileItem.file.name.replace(/\.pdf$/i, ""),
      courseId,
      courseName: selectedCourse?.title,
      progress: 0,
      status: "uploading",
      stage: "uploading",
      stageMessage: "Wird hochgeladen...",
    })

    let currentProgress = 0
    let progressTimeout: number | null = null

    const scheduleProgressTick = () => {
      progressTimeout = window.setTimeout(() => {
        currentProgress = Math.min(currentProgress + 10, 90)
        setFiles((prev) =>
          prev.map((file) =>
            file.id === fileItem.id ? { ...file, progress: currentProgress } : file
          )
        )
        backgroundTasks?.updateTask(tempTaskId, {
          progress: Math.round(currentProgress * 0.05),
          stageMessage: `Wird hochgeladen... ${currentProgress}%`,
        })

        if (currentProgress < 90) {
          scheduleProgressTick()
        }
      }, 200)
    }

    const stopProgressTick = () => {
      if (progressTimeout !== null) {
        clearTimeout(progressTimeout)
        progressTimeout = null
      }
    }

    try {
      try {
        const healthController = new AbortController()
        const healthTimeout = setTimeout(() => healthController.abort(), 5000)
        await fetch(`${apiUrl}/health`, {
          method: "GET",
          signal: healthController.signal,
        })
        clearTimeout(healthTimeout)
      } catch {
        backgroundTasks?.removeTask(tempTaskId)
        throw new Error(`Backend server is not reachable at ${apiUrl}. Please ensure the backend is running.`)
      }

      const formData = new FormData()
      formData.append("file", fileItem.file)
      formData.append("user_id", user.id)
      formData.append("course_id", courseId)

      scheduleProgressTick()

      const response = await fetch(`${apiUrl}/api/upload`, {
        method: "POST",
        body: formData,
      })

      stopProgressTick()

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Upload failed" }))
        backgroundTasks?.updateTask(tempTaskId, {
          status: "error",
          stageMessage: errorData.detail || "Upload fehlgeschlagen",
        })
        throw new Error(errorData.detail || `Upload failed: ${response.statusText}`)
      }

      const result = await response.json()

      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileItem.id
            ? {
                ...file,
                status: "processing",
                progress: 5,
                materialId: result.course_material_id,
              }
            : file
        )
      )

      if (backgroundTasks && result.course_material_id) {
        backgroundTasks.removeTask(tempTaskId)
        backgroundTasks.addTask({
          id: result.course_material_id,
          type: "pdf_processing",
          materialId: result.course_material_id,
          materialName: fileItem.file.name.replace(/\.pdf$/i, ""),
          courseId,
          courseName: selectedCourse?.title,
          progress: 5,
          status: "processing",
          stage: "processing",
          stageMessage: "Wird verarbeitet...",
        })
      }
    } catch (err) {
      stopProgressTick()
      let errorMessage = err instanceof Error ? err.message : "Upload fehlgeschlagen"

      if (err instanceof TypeError && err.message.includes("fetch")) {
        errorMessage = `Verbindung zum Server fehlgeschlagen. Bitte pruefen Sie, ob der Backend-Server unter ${apiUrl} laeuft.`
      }

      setFiles((prev) =>
        prev.map((file) =>
          file.id === fileItem.id ? { ...file, status: "error", errorMessage } : file
        )
      )

      backgroundTasks?.updateTask(tempTaskId, {
        status: "error",
        stageMessage: errorMessage,
      })

      throw err
    }
  }

  const onSubmit = async (data: CourseFormData) => {
    if (files.length === 0) {
      setError("Bitte waehlen Sie mindestens eine Datei aus")
      return
    }

    setIsUploading(true)
    setError(null)
    let hadUploadErrors = false

    try {
      let courseId = selectedCourseId

      if (mode === "create") {
        courseId = await createCourse(data)
        setSelectedCourseId(courseId)
      }

      if (!courseId) {
        throw new Error("Kein Kurs ausgewaehlt")
      }

      const pendingFiles = files.filter((file) => file.status === "pending" || file.status === "error")

      for (const fileItem of pendingFiles) {
        try {
          await uploadSingleFile(fileItem, courseId)
          toast.success(`${fileItem.file.name} erfolgreich hochgeladen`)
        } catch (err) {
          hadUploadErrors = true
          const errorMessage = err instanceof Error ? err.message : "Upload fehlgeschlagen"
          toast.error(`Fehler bei ${fileItem.file.name}`, {
            description: errorMessage,
          })
        }
      }

      if (!hadUploadErrors) {
        toast.success("Alle Dateien erfolgreich hochgeladen!")
        window.setTimeout(() => {
          setOpen(false)
          window.location.reload()
        }, 2000)
      } else {
        toast.warning("Einige Dateien konnten nicht hochgeladen werden")
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Ein Fehler ist aufgetreten"
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setIsUploading(false)
    }
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (isUploading) {
      toast.warning("Upload laeuft noch. Bitte warten Sie, bis alle Dateien hochgeladen sind.")
      return
    }

    setOpen(nextOpen)
    if (!nextOpen) {
      reset()
      setFiles([])
      setSelectedCourseId("")
      setError(null)
      setMode("select")
    }
  }

  const getOverallProgress = () => {
    if (files.length === 0) {
      return 0
    }

    const totalProgress = files.reduce(
      (sum, file) => sum + (file.processingProgress ?? file.progress ?? 0),
      0
    )
    return Math.round(totalProgress / files.length)
  }

  const completedCount = files.filter((file) => file.status === "completed").length
  const errorCount = files.filter((file) => file.status === "error").length
  const uploadingCount = files.filter(
    (file) => file.status === "uploading" || file.status === "processing"
  ).length

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Materialien hochladen
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>Materialien hochladen</DialogTitle>
          <DialogDescription>
            Erstellen Sie einen neuen Kurs oder waehlen Sie einen bestehenden aus und laden Sie PDF-Dateien hoch.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="files" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="files">Dateien auswaehlen</TabsTrigger>
            <TabsTrigger value="status" disabled={files.length === 0}>
              Upload-Status ({files.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="files" className="space-y-4">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label>Kurs</Label>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant={mode === "select" ? "default" : "outline"}
                    onClick={() => setMode("select")}
                    className="flex-1"
                  >
                    Vorhandenen waehlen
                  </Button>
                  <Button
                    type="button"
                    variant={mode === "create" ? "default" : "outline"}
                    onClick={() => setMode("create")}
                    className="flex-1"
                  >
                    Neuen erstellen
                  </Button>
                </div>
              </div>

              {mode === "select" && (
                <div className="space-y-2">
                  <Label htmlFor="course-select">Kurs auswaehlen</Label>
                  <Select value={selectedCourseId} onValueChange={setSelectedCourseId} required>
                    <SelectTrigger id="course-select">
                      <SelectValue placeholder="Kurs waehlen" />
                    </SelectTrigger>
                    <SelectContent>
                      {courses.length === 0 ? (
                        <SelectItem value="no-course" disabled>
                          Keine Kurse verfuegbar
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

              {mode === "create" && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Kursname *</Label>
                    <Input
                      id="title"
                      {...register("title", { required: "Kursname ist erforderlich" })}
                      placeholder="z.B. Marketing 101"
                    />
                    {errors.title && <p className="text-sm text-red-600">{errors.title.message}</p>}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Beschreibung</Label>
                    <Input
                      id="description"
                      {...register("description")}
                      placeholder="Optionale Kursbeschreibung"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="exam_date">Pruefungsdatum</Label>
                    <Input id="exam_date" type="date" {...register("exam_date")} />
                  </div>
                </div>
              )}

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
                    <Button type="button" variant="outline" size="sm" onClick={handleRemoveAll} disabled={isUploading}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Alle entfernen
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Mehrere Dateien moeglich. Max. {MAX_FILES} Dateien, je max. {MAX_FILE_SIZE / 1024 / 1024}MB.
                </p>
              </div>

              {files.length > 0 && (
                <div className="space-y-2">
                  <Label>Ausgewaehlte Dateien ({files.length})</Label>
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
                    Dateien koennen per Drag and Drop neu sortiert werden.
                  </p>
                </div>
              )}

              {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}

              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isUploading}>
                  Abbrechen
                </Button>
                <Button
                  type="submit"
                  disabled={isUploading || files.length === 0 || (mode === "select" && !selectedCourseId)}
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
                        ? `${files.length} Datei${files.length > 1 ? "en" : ""} hochladen`
                        : "Hochladen"}
                    </>
                  )}
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>

          <TabsContent value="status" className="space-y-4">
            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Gesamtfortschritt</span>
                  <span className="text-muted-foreground">
                    {completedCount} von {files.length} Dateien fertig
                  </span>
                </div>
                <Progress value={getOverallProgress()} className="h-2" />
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Fertig: {completedCount}</span>
                  <span>Laeuft: {uploadingCount}</span>
                  <span>Fehler: {errorCount}</span>
                  <span>Wartend: {files.length - completedCount - uploadingCount - errorCount}</span>
                </div>
              </div>

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
