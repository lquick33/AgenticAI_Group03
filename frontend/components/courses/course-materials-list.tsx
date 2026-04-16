"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { BookOpen, Download, Loader2, MoreVertical, Play, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { useBackgroundTasksOptional } from "@/components/background-tasks"
import { EditableFilename } from "@/components/courses/editable-filename"
import { DeckCompletionDialog } from "@/components/study/deck-completion-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Progress } from "@/components/ui/progress"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { CourseMaterial } from "@/types"
import { deleteMaterial } from "@/lib/api/materials"
import {
  downloadFlashcardsFromDb,
  generateFlashcards,
  getActiveFlashcardTask,
  getFlashcardsForMaterial,
  type FlashcardTaskStatus,
} from "@/lib/api/study"
import {
  getFlashcardTaskForMaterial,
  isFinalBackgroundTaskStatus,
  toFlashcardTaskStatus,
} from "@/lib/background-task-utils"

interface CourseMaterialsListProps {
  materials: CourseMaterial[]
  courseId: string
  userId: string
  onMaterialDeleted?: () => void
  materialProgress?: Record<string, { progress: number; stage: string; stageMessage: string }>
  deduplicateFlashcards?: boolean
}

export function CourseMaterialsList({
  materials,
  courseId,
  userId,
  onMaterialDeleted,
  materialProgress = {},
  deduplicateFlashcards = false,
}: CourseMaterialsListProps) {
  const [localMaterials, setLocalMaterials] = useState<CourseMaterial[]>(materials)
  const [flashcardsStatus, setFlashcardsStatus] = useState<Record<string, boolean>>({})
  const [loadingFlashcards, setLoadingFlashcards] = useState<Record<string, boolean>>({})
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [materialIdForGeneration, setMaterialIdForGeneration] = useState<string | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [materialIdForDeletion, setMaterialIdForDeletion] = useState<string | null>(null)
  const [materialNameForDeletion, setMaterialNameForDeletion] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completedMaterialId, setCompletedMaterialId] = useState<string | null>(null)
  const [completedStatus, setCompletedStatus] = useState<FlashcardTaskStatus | null>(null)
  const [isDialogDownloading, setIsDialogDownloading] = useState(false)
  const [dialogDownloadSuccess, setDialogDownloadSuccess] = useState(false)
  const backgroundTasks = useBackgroundTasksOptional()
  const restoredFlashcardTasksRef = useRef<Set<string>>(new Set())
  const previousFlashcardStatusesRef = useRef<Map<string, string>>(new Map())

  useEffect(() => {
    setLocalMaterials(materials)
  }, [materials])

  useEffect(() => {
    const initialStatus: Record<string, boolean> = {}
    localMaterials.forEach((material) => {
      initialStatus[material.id] = material.has_flashcards ?? false
    })
    setFlashcardsStatus(initialStatus)
  }, [localMaterials])

  const flashcardTaskByMaterial = useMemo(() => {
    const taskMap = new Map<string, ReturnType<typeof getFlashcardTaskForMaterial>>()
    backgroundTasks?.tasks.forEach((task) => {
      if (task.type === "flashcard_generation") {
        taskMap.set(task.materialId, task)
      }
    })
    return taskMap
  }, [backgroundTasks?.tasks])

  const handleGenerationComplete = useCallback((materialId: string, status: FlashcardTaskStatus) => {
    setFlashcardsStatus((prev) => ({ ...prev, [materialId]: true }))
    setCompletedMaterialId(materialId)
    setCompletedStatus(status)
    setDialogDownloadSuccess(false)
    setShowCompletionDialog(true)
  }, [])

  useEffect(() => {
    const flashcardTasks = Array.from(flashcardTaskByMaterial.values()).filter(Boolean)
    const nextStatuses = new Map<string, string>()

    flashcardTasks.forEach((task) => {
      if (!task) {
        return
      }

      nextStatuses.set(task.materialId, task.status)
      const previousStatus = previousFlashcardStatusesRef.current.get(task.materialId)
      if (!previousStatus || previousStatus === task.status) {
        return
      }

      if (task.status === "completed") {
        handleGenerationComplete(task.materialId, toFlashcardTaskStatus(task))
      }
    })

    previousFlashcardStatusesRef.current = nextStatuses
  }, [flashcardTaskByMaterial, handleGenerationComplete])

  useEffect(() => {
    if (!backgroundTasks) {
      return
    }

    localMaterials.forEach((material) => {
      if (
        material.processing_status !== "completed" ||
        restoredFlashcardTasksRef.current.has(material.id)
      ) {
        return
      }

      restoredFlashcardTasksRef.current.add(material.id)

      void (async () => {
        try {
          const activeTask = await getActiveFlashcardTask(material.id, userId)
          if (!activeTask) {
            return
          }

          if (activeTask.status === "pending" || activeTask.status === "running") {
            backgroundTasks.addTask({
              id: `flashcard-${material.id}`,
              type: "flashcard_generation",
              materialId: material.id,
              materialName: material.file_name.replace(/\.pdf$/i, "") || "Unbekannt",
              courseId,
              progress: Math.round(activeTask.progress * 100),
              status: activeTask.status,
              stageMessage:
                activeTask.status === "pending"
                  ? "Warte auf Start..."
                  : `Seite ${activeTask.processed_pages} von ${activeTask.total_pages}`,
              taskId: activeTask.task_id,
              totalPages: activeTask.total_pages,
              completedPages: activeTask.processed_pages,
              cardsGenerated: activeTask.cards_generated,
              ankiSynced: activeTask.anki_synced,
              ankiWebSynced: activeTask.ankiweb_synced,
            })
          } else if (activeTask.status === "completed") {
            setFlashcardsStatus((prev) => ({ ...prev, [material.id]: true }))
          }
        } catch (error) {
          console.error(`Error checking active task for material ${material.id}:`, error)
        }
      })()
    })
  }, [backgroundTasks, courseId, localMaterials, userId])

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const handleDownloadFlashcards = async (materialId: string) => {
    setLoadingFlashcards((prev) => ({ ...prev, [materialId]: true }))
    try {
      const { blob, filename } = await downloadFlashcardsFromDb(materialId, userId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(link)
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
      setLoadingFlashcards((prev) => ({ ...prev, [materialId]: false }))
    }
  }

  const handleGenerateFlashcards = async (materialId: string) => {
    setShowConfirmDialog(false)
    setMaterialIdForGeneration(null)

    try {
      const { task_id } = await generateFlashcards(materialId, userId, deduplicateFlashcards)
      const material = localMaterials.find((entry) => entry.id === materialId)

      backgroundTasks?.addTask({
        id: `flashcard-${materialId}`,
        type: "flashcard_generation",
        materialId,
        materialName: material?.file_name?.replace(/\.pdf$/i, "") || "Unbekannt",
        courseId,
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
    }
  }

  const handleDownloadButtonClick = async (materialId: string) => {
    if (flashcardsStatus[materialId]) {
      void handleDownloadFlashcards(materialId)
      return
    }

    try {
      const result = await getFlashcardsForMaterial(materialId, userId)
      if (result.count > 0) {
        setFlashcardsStatus((prev) => ({ ...prev, [materialId]: true }))
        void handleDownloadFlashcards(materialId)
        return
      }
    } catch {
      // No flashcards yet, fall through to dialog.
    }

    setMaterialIdForGeneration(materialId)
    setShowConfirmDialog(true)
  }

  const getStatusBadge = (material: CourseMaterial) => {
    const status = material.processing_status
    const progress = materialProgress[material.id]

    switch (status) {
      case "uploading":
        return (
          <div className="space-y-2">
            <Badge variant="info">Wird hochgeladen</Badge>
            {progress ? (
              <div className="min-w-[140px] space-y-1">
                <Progress value={progress.progress} className="h-1.5 w-full" />
                <p className="text-xs text-muted-foreground">{progress.progress}%</p>
              </div>
            ) : null}
          </div>
        )
      case "processing":
        return (
          <div className="min-w-[150px] space-y-2">
            <Badge variant="warning">Wird verarbeitet</Badge>
            {progress ? (
              <div className="space-y-1">
                <Progress value={progress.progress} className="h-1.5" />
                <p className="text-xs text-muted-foreground">{progress.stageMessage}</p>
              </div>
            ) : null}
          </div>
        )
      case "completed":
        return <Badge variant="success">Abgeschlossen</Badge>
      case "error":
        return <Badge variant="destructive">Fehler</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const handleFilenameUpdate = (materialId: string, newFilename: string) => {
    setLocalMaterials((prev) =>
      prev.map((material) =>
        material.id === materialId ? { ...material, file_name: newFilename } : material
      )
    )
  }

  const handleDeleteClick = (materialId: string, materialName: string) => {
    setMaterialIdForDeletion(materialId)
    setMaterialNameForDeletion(materialName)
    setShowDeleteDialog(true)
  }

  const handleDeleteMaterial = async () => {
    if (!materialIdForDeletion) {
      return
    }

    setIsDeleting(true)
    try {
      await deleteMaterial(materialIdForDeletion, userId)
      setLocalMaterials((prev) => prev.filter((material) => material.id !== materialIdForDeletion))

      setFlashcardsStatus((prev) => {
        const updated = { ...prev }
        delete updated[materialIdForDeletion]
        return updated
      })
      setLoadingFlashcards((prev) => {
        const updated = { ...prev }
        delete updated[materialIdForDeletion]
        return updated
      })

      backgroundTasks?.removeTask(materialIdForDeletion)
      backgroundTasks?.removeTask(`flashcard-${materialIdForDeletion}`)

      toast.success("Material geloescht", {
        description: "Das Material wurde erfolgreich geloescht.",
      })

      onMaterialDeleted?.()
      setShowDeleteDialog(false)
      setMaterialIdForDeletion(null)
      setMaterialNameForDeletion(null)
    } catch (error) {
      console.error("Error deleting material:", error)
      toast.error("Fehler beim Loeschen", {
        description:
          error instanceof Error ? error.message : "Das Material konnte nicht geloescht werden.",
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDialogDownload = async () => {
    if (!completedMaterialId) {
      return
    }

    setIsDialogDownloading(true)
    try {
      const { blob, filename } = await downloadFlashcardsFromDb(completedMaterialId, userId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(link)

      setDialogDownloadSuccess(true)
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
      setIsDialogDownloading(false)
    }
  }

  const handleCloseCompletionDialog = () => {
    setShowCompletionDialog(false)
    setCompletedMaterialId(null)
    setCompletedStatus(null)
    setDialogDownloadSuccess(false)
  }

  if (localMaterials.length === 0) {
    return (
      <div className="app-surface-panel app-empty-state min-h-[220px]">
        <p className="text-base font-medium text-foreground">Noch keine Materialien hochgeladen.</p>
        <p className="max-w-md text-sm text-muted-foreground">
          Sobald du dein erstes PDF hochlaedst, erscheinen hier Status, Study-Einstieg und Flashcard-Aktionen.
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="app-table-shell">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Dateiname</TableHead>
              <TableHead>Seiten</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Hochgeladen am</TableHead>
              <TableHead className="text-right">Aktionen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {localMaterials.map((material) => {
              const flashcardTask = flashcardTaskByMaterial.get(material.id)
              const activeFlashcardTask =
                flashcardTask && !isFinalBackgroundTaskStatus(flashcardTask.status)
              const flashcardTaskStatus = flashcardTask ? toFlashcardTaskStatus(flashcardTask) : null

              return (
                <TableRow key={material.id}>
                  <TableCell className="min-w-[250px] align-top">
                    <div className="space-y-1">
                      <EditableFilename
                        materialId={material.id}
                        userId={userId}
                        initialFilename={material.file_name}
                        onUpdate={(newFilename) => handleFilenameUpdate(material.id, newFilename)}
                      />
                      <p className="text-xs text-muted-foreground">Material-ID: {material.id.slice(0, 8)}</p>
                    </div>
                  </TableCell>
                  <TableCell className="align-top font-medium text-foreground">{material.page_count}</TableCell>
                  <TableCell className="align-top">{getStatusBadge(material)}</TableCell>
                  <TableCell className="align-top text-sm text-muted-foreground">
                    {formatDate(material.created_at)}
                  </TableCell>
                  <TableCell className="align-top text-right">
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      {material.processing_status === "completed" ? (
                        <>
                          <Button asChild variant="outline" size="sm">
                            <Link href={`/dashboard/courses/${courseId}/study/${material.id}`}>
                              <BookOpen className="h-4 w-4" />
                              Studieren
                            </Link>
                          </Button>
                          <Button
                            variant="accent"
                            size="sm"
                            disabled={loadingFlashcards[material.id] || Boolean(activeFlashcardTask)}
                            onClick={() => void handleDownloadButtonClick(material.id)}
                          >
                            {activeFlashcardTask ? (
                              <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                {flashcardTaskStatus?.progress !== undefined
                                  ? `Wird erstellt... ${Math.round(flashcardTaskStatus.progress * 100)}%`
                                  : "Wird erstellt..."}
                              </>
                            ) : (
                              <>
                                {flashcardsStatus[material.id] ? (
                                  <Download className="h-4 w-4" />
                                ) : (
                                  <Play className="h-4 w-4" />
                                )}
                                Flashcards
                              </>
                            )}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variant="outline" size="sm" disabled>
                            <BookOpen className="h-4 w-4" />
                            Studieren
                          </Button>
                          <Button variant="accent" size="sm" disabled>
                            <Play className="h-4 w-4" />
                            Flashcards
                          </Button>
                        </>
                      )}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon-touch"
                            aria-label={`Optionen fuer ${material.file_name}`}
                          >
                            <span className="sr-only">Mehr Optionen</span>
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            className="cursor-pointer text-destructive focus:text-destructive"
                            onClick={() => handleDeleteClick(material.id, material.file_name)}
                            disabled={isDeleting}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Loeschen
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Karteikarten erstellen</DialogTitle>
            <DialogDescription>
              Fuer die beste Qualitaet lohnt es sich, das Material zuerst im Study Reader mit dem Tutor durchzugehen. Du kannst die Generierung trotzdem schon jetzt starten.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowConfirmDialog(false)
                setMaterialIdForGeneration(null)
              }}
            >
              Abbrechen
            </Button>
            <Button
              variant="accent"
              onClick={() => {
                if (materialIdForGeneration) {
                  void handleGenerateFlashcards(materialIdForGeneration)
                }
              }}
            >
              Weiter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Material loeschen</DialogTitle>
            <DialogDescription>
              Bist du sicher, dass du &quot;{materialNameForDeletion}&quot; loeschen moechtest? Diese Aktion kann nicht rueckgaengig gemacht werden. Alle zugehoerigen Daten werden ebenfalls geloescht.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowDeleteDialog(false)
                setMaterialIdForDeletion(null)
                setMaterialNameForDeletion(null)
              }}
              disabled={isDeleting}
            >
              Abbrechen
            </Button>
            <Button variant="destructive" onClick={() => void handleDeleteMaterial()} disabled={isDeleting}>
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Wird geloescht...
                </>
              ) : (
                "Loeschen"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DeckCompletionDialog
        isOpen={showCompletionDialog}
        onClose={handleCloseCompletionDialog}
        status={completedStatus}
        onDownload={handleDialogDownload}
        isDownloading={isDialogDownloading}
        downloadSuccess={dialogDownloadSuccess}
      />
    </>
  )
}
