"use client"

import { useEffect, useRef, useState } from "react"
import { CheckCircle2, Download, Loader2, X } from "lucide-react"
import { toast } from "sonner"

import { useBackgroundTasksOptional } from "@/components/background-tasks"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { DeckCompletionDialog } from "./deck-completion-dialog"
import {
  cancelFlashcardTask,
  downloadFlashcards,
  generateFlashcards,
  getActiveFlashcardTask,
  type FlashcardTaskStatus,
} from "@/lib/api/study"
import { getFlashcardTaskForMaterial, toFlashcardTaskStatus } from "@/lib/background-task-utils"

interface CongratulationsScreenProps {
  materialId: string
  materialName?: string
  courseId: string
  courseName?: string
  userId: string
  onClose?: () => void
}

export function CongratulationsScreen({
  materialId,
  materialName,
  courseId,
  courseName,
  userId,
  onClose,
}: CongratulationsScreenProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [downloadSuccess, setDownloadSuccess] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState<FlashcardTaskStatus | null>(null)
  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completedStatus, setCompletedStatus] = useState<FlashcardTaskStatus | null>(null)
  const backgroundTasks = useBackgroundTasksOptional()
  const restoredTaskRef = useRef(false)
  const previousStatusRef = useRef<string | null>(null)

  const currentTask = getFlashcardTaskForMaterial(backgroundTasks?.tasks, materialId)

  useEffect(() => {
    if (!currentTask) {
      previousStatusRef.current = null
      return
    }

    const mappedStatus = toFlashcardTaskStatus(currentTask)
    setTaskId(currentTask.taskId ?? currentTask.id)
    setTaskStatus(mappedStatus)

    const previousStatus = previousStatusRef.current
    previousStatusRef.current = currentTask.status

    if (currentTask.status === "completed") {
      setIsGenerating(false)
      if (previousStatus && previousStatus !== currentTask.status) {
        setCompletedStatus(mappedStatus)
        setShowCompletionDialog(true)
      }
      return
    }

    if (currentTask.status === "failed" || currentTask.status === "cancelled" || currentTask.status === "error") {
      setIsGenerating(false)
      return
    }

    setIsGenerating(true)
  }, [currentTask])

  useEffect(() => {
    if (restoredTaskRef.current || currentTask) {
      return
    }

    restoredTaskRef.current = true

    void (async () => {
      try {
        const activeTask = await getActiveFlashcardTask(materialId, userId)
        if (!activeTask) {
          return
        }

        setTaskId(activeTask.task_id)
        setTaskStatus(activeTask)
        setIsGenerating(activeTask.status === "pending" || activeTask.status === "running")

        if (activeTask.status === "completed") {
          setCompletedStatus(activeTask)
        }

        backgroundTasks?.addTask({
          id: `flashcard-${materialId}`,
          type: "flashcard_generation",
          materialId,
          materialName: materialName || "Vorlesung",
          courseId,
          courseName,
          progress: Math.round(activeTask.progress * 100),
          status: activeTask.status === "failed" ? "failed" : activeTask.status,
          stageMessage:
            activeTask.status === "pending"
              ? "Warte auf Start..."
              : activeTask.status === "running"
                ? `Seite ${activeTask.processed_pages} von ${activeTask.total_pages}`
                : `${activeTask.cards_generated} Karten erstellt`,
          taskId: activeTask.task_id,
          totalPages: activeTask.total_pages,
          completedPages: activeTask.processed_pages,
          cardsGenerated: activeTask.cards_generated,
          ankiSynced: activeTask.anki_synced,
          ankiWebSynced: activeTask.ankiweb_synced,
        })
      } catch (error) {
        console.error("Error restoring flashcard task:", error)
      }
    })()
  }, [backgroundTasks, courseId, courseName, currentTask, materialId, materialName, userId])

  const handleDownload = async () => {
    if (!taskId) {
      return
    }

    setIsDownloading(true)
    try {
      const { blob, filename } = await downloadFlashcards(taskId, userId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      setDownloadSuccess(true)
      toast.success("Flashcards heruntergeladen", {
        description: "Die Karteikarten wurden erfolgreich heruntergeladen.",
      })
    } catch (error) {
      console.error("Error downloading flashcards:", error)
      toast.error("Fehler beim Download", {
        description:
          error instanceof Error
            ? error.message
            : "Die Karteikarten konnten nicht heruntergeladen werden.",
      })
    } finally {
      setIsDownloading(false)
    }
  }

  const handleCancel = async () => {
    if (!taskId) {
      return
    }

    try {
      if (currentTask && backgroundTasks) {
        await backgroundTasks.cancelTask(currentTask.id)
      } else {
        await cancelFlashcardTask(taskId, userId)
      }

      setIsGenerating(false)
      setTaskId(null)
      setTaskStatus(null)
      backgroundTasks?.removeTask(`flashcard-${materialId}`)

      toast.info("Generierung abgebrochen", {
        description: "Die Karteikarten-Generierung wurde abgebrochen.",
      })
    } catch (error) {
      console.error("Error cancelling task:", error)
      toast.error("Fehler beim Abbrechen", {
        description: "Die Generierung konnte nicht abgebrochen werden.",
      })
    }
  }

  const handleGenerateFlashcards = async () => {
    setIsGenerating(true)
    setDownloadSuccess(false)
    setTaskStatus(null)
    setCompletedStatus(null)

    try {
      const { task_id } = await generateFlashcards(materialId, userId)
      setTaskId(task_id)

      backgroundTasks?.addTask({
        id: `flashcard-${materialId}`,
        type: "flashcard_generation",
        materialId,
        materialName: materialName || "Vorlesung",
        courseId,
        courseName,
        progress: 0,
        status: "running",
        stageMessage: "Wird gestartet...",
        taskId: task_id,
      })

      toast.info("Generierung gestartet", {
        description: "Die Karteikarten werden im Hintergrund generiert.",
      })
    } catch (error) {
      console.error("Error starting flashcard generation:", error)
      toast.error("Fehler beim Starten", {
        description:
          error instanceof Error
            ? error.message
            : "Die Generierung konnte nicht gestartet werden.",
      })
      setIsGenerating(false)
    }
  }

  return (
    <>
      <DeckCompletionDialog
        isOpen={showCompletionDialog}
        onClose={() => setShowCompletionDialog(false)}
        status={completedStatus}
        onDownload={handleDownload}
        isDownloading={isDownloading}
        downloadSuccess={downloadSuccess}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
        <Card className="mx-4 w-full max-w-2xl bg-white/85">
          <CardHeader className="text-center">
            <div className="mb-4 flex justify-center">
              <CheckCircle2 className="h-16 w-16 text-green-500" />
            </div>
            <CardTitle className="text-3xl">Herzlichen Glueckwunsch!</CardTitle>
            <CardDescription className="mt-2 text-lg">
              Du hast die Vorlesung erfolgreich durchgearbeitet.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-center text-muted-foreground">
              Du kannst jetzt deine persoenlichen Karteikarten herunterladen, die auf Basis der Vorlesungsinhalte und deiner Konversationen mit dem Tutor erstellt wurden.
            </p>

            <div className="flex flex-col gap-4">
              {isGenerating && taskStatus && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      {taskStatus.status === "running"
                        ? `Seite ${taskStatus.processed_pages} von ${taskStatus.total_pages} verarbeitet...`
                        : "Wird vorbereitet..."}
                    </span>
                    <span className="font-medium">{Math.round(taskStatus.progress * 100)}%</span>
                  </div>
                  <Progress value={taskStatus.progress * 100} className="h-2" />
                  {taskStatus.cards_generated > 0 && (
                    <p className="text-center text-xs text-muted-foreground">
                      {taskStatus.cards_generated} Karteikarten generiert
                    </p>
                  )}
                </div>
              )}

              <Button
                onClick={() => void handleGenerateFlashcards()}
                disabled={isGenerating || completedStatus !== null}
                size="lg"
                variant="accent"
                className="w-full"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Karteikarten werden erstellt...
                  </>
                ) : completedStatus !== null ? (
                  <>
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Karteikarten erstellt
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Flashcards erstellen
                  </>
                )}
              </Button>

              {completedStatus !== null && (
                <Button onClick={() => setShowCompletionDialog(true)} variant="outline" size="lg" className="w-full">
                  Status anzeigen
                </Button>
              )}

              {isGenerating && taskId && (
                <Button onClick={() => void handleCancel()} variant="outline" size="sm" className="w-full">
                  <X className="mr-2 h-4 w-4" />
                  Abbrechen
                </Button>
              )}

              {onClose && (
                <Button onClick={onClose} variant="outline" size="lg" className="w-full">
                  Zurueck zur Vorlesung
                </Button>
              )}
            </div>

            <div className="text-center text-sm text-muted-foreground">
              <p>
                Die Karteikarten koennen direkt in Anki importiert werden.
                <br />
                Format: .apkg (Anki-Deck mit eingebetteten Bildern)
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
