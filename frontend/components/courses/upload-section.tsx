"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { CheckCircle2, FileText, Loader2, Trash2, Upload, X, XCircle } from "lucide-react"
import { toast } from "sonner"

import { useBackgroundTasksOptional } from "@/components/background-tasks"
import {
  MultiFileUploadList,
  type FileUploadItem,
} from "@/components/courses/multi-file-upload-list"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { getApiUrl } from "@/lib/public-env"
import { mergeFilesWithPdfTasks } from "@/lib/upload-task-utils"

interface UploadSectionProps {
  courseId: string
  userId: string
  courseName?: string
  onUploadSuccess?: () => void
}

const MAX_FILE_SIZE = 50 * 1024 * 1024
const MAX_FILES = 20

export function UploadSection({ courseId, userId, courseName, onUploadSuccess }: UploadSectionProps) {
  const [files, setFiles] = useState<FileUploadItem[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const backgroundTasks = useBackgroundTasksOptional()

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
      const message = `Maximal ${MAX_FILES} Dateien gleichzeitig`
      setError(message)
      toast.error(message)
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

      if (
        files.some(
          (candidate) => candidate.file.name === file.name && candidate.file.size === file.size
        )
      ) {
        errors.push(`${file.name}: Datei bereits hinzugefuegt`)
        return
      }

      newFiles.push({
        id: `${Date.now()}-${Math.random()}`,
        file,
        status: "pending",
        order: files.length + newFiles.length + 1,
      })
    })

    if (errors.length > 0) {
      setError(errors.join(", "))
      toast.error("Einige Dateien konnten nicht hinzugefuegt werden", {
        description: errors.slice(0, 3).join("; "),
      })
    }

    if (newFiles.length > 0) {
      setFiles((prev) => [...prev, ...newFiles])
      setError(null)
      toast.success(`${newFiles.length} Datei${newFiles.length > 1 ? "en" : ""} hinzugefuegt`)
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
    if (!fileItem) {
      return
    }

    await uploadSingleFile(fileItem)
  }

  const handleRemoveAll = () => {
    setFiles([])
    setError(null)
  }

  const uploadSingleFile = async (fileItem: FileUploadItem): Promise<void> => {
    const tempTaskId = `upload-${fileItem.id}`
    const apiUrl = getApiUrl()

    setFiles((prev) =>
      prev.map((file) =>
        file.id === fileItem.id ? { ...file, status: "uploading", progress: 0 } : file
      )
    )

    if (backgroundTasks) {
      backgroundTasks.addTask({
        id: tempTaskId,
        type: "pdf_processing",
        materialId: tempTaskId,
        materialName: fileItem.file.name.replace(/\.pdf$/i, ""),
        courseId,
        courseName,
        progress: 0,
        status: "uploading",
        stage: "uploading",
        stageMessage: "Wird hochgeladen...",
      })
    }

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
      formData.append("user_id", userId)
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
          courseName,
          progress: 5,
          status: "processing",
          stage: "processing",
          stageMessage: "Wird verarbeitet...",
        })
      }

      onUploadSuccess?.()
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

  const handleUpload = async () => {
    if (files.length === 0) {
      setError("Bitte waehlen Sie mindestens eine Datei aus")
      return
    }

    setIsUploading(true)
    setError(null)

    let hadUploadErrors = false

    try {
      const pendingFiles = files.filter(
        (file) => file.status === "pending" || file.status === "error"
      )

      for (const fileItem of pendingFiles) {
        try {
          await uploadSingleFile(fileItem)
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
          router.refresh()
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

  const activeCourseTasks =
    backgroundTasks?.getTasksByCourse(courseId).filter(
      (task) =>
        task.type === "pdf_processing" &&
        !["completed", "failed", "cancelled", "error"].includes(task.status)
    ) || []

  const recentCourseTasks =
    backgroundTasks?.getTasksByCourse(courseId).filter((task) => {
      if (task.type !== "pdf_processing") {
        return false
      }
      if (!["completed", "failed", "cancelled", "error"].includes(task.status)) {
        return false
      }
      const isInLocalFiles = files.some((file) => file.materialId === task.materialId)
      if (isInLocalFiles) {
        return false
      }
      const age = new Date().getTime() - new Date(task.createdAt).getTime()
      return age < 30000
    }) || []

  const globalTasksToShow = [...activeCourseTasks, ...recentCourseTasks].filter(
    (task) => !files.some((file) => file.materialId === task.materialId || file.materialId === task.id)
  )

  return (
    <div className="app-surface-panel app-surface-panel--muted gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <h4 className="text-lg font-semibold tracking-tight text-foreground">Vorlesungsmaterial hochladen</h4>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Ziehe PDFs in die Ablage, ordne sie bei Bedarf neu und starte den Upload gesammelt als sauberen Batch.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="app-subtle-chip">Max. {MAX_FILES} Dateien</span>
          <span className="app-subtle-chip">Bis {MAX_FILE_SIZE / 1024 / 1024} MB pro PDF</span>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="space-y-4">
        <label
          htmlFor="file-upload"
          className="flex min-h-40 w-full cursor-pointer flex-col items-center justify-center rounded-[1.5rem] border border-dashed border-[var(--app-border-strong)] bg-[linear-gradient(180deg,rgba(255,255,255,0.65),rgba(255,255,255,0.35))] px-6 py-8 text-center transition-colors hover:border-[var(--app-accent)] hover:bg-[var(--app-surface)]"
        >
          <div className="flex flex-col items-center justify-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--app-surface)] shadow-[var(--app-shadow-soft)]">
              <Upload className="h-5 w-5 text-[var(--app-accent)]" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">
                Klicke zum Hochladen oder ziehe die Dateien hierher
              </p>
              <p className="text-xs text-muted-foreground">
                Nur PDFs, gesammelt im Batch und spaeter im Kursraum organisiert.
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
          </div>
        </label>

        {globalTasksToShow.length > 0 ? (
          <div className="space-y-3">
            <Label className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-[var(--app-accent)]" />
              Laufende Verarbeitungen ({globalTasksToShow.length})
            </Label>
            <div className="space-y-2">
              {globalTasksToShow.map((task) => {
                const isActive = !["completed", "failed", "cancelled", "error"].includes(task.status)
                return (
                  <div
                    key={task.id}
                    className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface)] p-4 shadow-[var(--app-shadow-soft)]"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--app-surface-subtle)]">
                        <FileText className="h-4 w-4 text-[var(--app-accent)]" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-foreground">{task.materialName}</p>
                        <p className="text-xs text-muted-foreground">
                          {task.stageMessage || "Wird verarbeitet..."}
                        </p>
                      </div>
                      {task.status === "completed" ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                      ) : task.status === "error" || task.status === "failed" ? (
                        <XCircle className="h-4 w-4 shrink-0 text-red-500" />
                      ) : (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--app-accent)]" />
                      )}
                    </div>
                    <div className="mt-3 space-y-2">
                      <Progress value={task.progress} className="h-2" />
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>{task.stageMessage || "Wird verarbeitet..."}</span>
                        <span className="font-medium">{task.progress}%</span>
                      </div>
                    </div>
                    {!isActive || task.status === "uploading" ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-3 text-muted-foreground hover:text-foreground"
                        onClick={() => backgroundTasks?.removeTask(task.id)}
                      >
                        <X className="h-3.5 w-3.5" />
                        {task.status === "uploading" ? "Abbrechen" : "Aus Ansicht entfernen"}
                      </Button>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>
        ) : null}

        {files.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Label className="text-sm font-medium text-foreground">
                Ausgewaehlte Dateien ({files.length})
              </Label>
              <Button variant="outline" size="sm" onClick={handleRemoveAll} disabled={isUploading}>
                <Trash2 className="h-4 w-4" />
                Alle entfernen
              </Button>
            </div>
            <div className="max-h-[320px] overflow-y-auto rounded-[1.25rem] border border-[var(--app-border-soft)] bg-[var(--app-surface)] p-2">
              <MultiFileUploadList
                files={files}
                onReorder={handleReorderFiles}
                onRemove={handleRemoveFile}
                onRetry={handleRetryUpload}
                disabled={isUploading}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Dateien koennen per Drag and Drop in die gewuenschte Reihenfolge gebracht werden.
            </p>
          </div>
        ) : null}

        {isUploading && files.length > 0 ? (
          <div className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface)] p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">Gesamtfortschritt</span>
              <span className="text-muted-foreground">
                {completedCount} von {files.length} Dateien fertig
              </span>
            </div>
            <Progress value={getOverallProgress()} className="mt-3 h-2" />
            <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
              <span>Fertig: {completedCount}</span>
              <span>Laeuft: {uploadingCount}</span>
              <span>Fehler: {errorCount}</span>
              <span>Wartend: {files.length - completedCount - uploadingCount - errorCount}</span>
            </div>
          </div>
        ) : null}

        <Button onClick={handleUpload} disabled={files.length === 0 || isUploading} variant="accent" className="w-full">
          {isUploading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Wird hochgeladen...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              {files.length > 0
                ? `${files.length} Datei${files.length > 1 ? "en" : ""} hochladen`
                : "Hochladen"}
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
