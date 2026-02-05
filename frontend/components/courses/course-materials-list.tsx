"use client"

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { BookOpen, Download, Loader2, MoreVertical, Play, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { CourseMaterial } from '@/types'
import {
  getFlashcardsForMaterial,
  downloadFlashcardsFromDb,
  generateFlashcards,
  getFlashcardTaskStatus,
  downloadFlashcards,
  cancelFlashcardTask,
  getActiveFlashcardTask,
  type FlashcardTaskStatus,
} from '@/lib/api/study'
import { EditableFilename } from '@/components/courses/editable-filename'
import { DeckCompletionDialog } from '@/components/study/deck-completion-dialog'
import { toast } from 'sonner'
import { deleteMaterial } from '@/lib/api/materials'
import { useBackgroundTasksOptional } from '@/components/background-tasks'

interface CourseMaterialsListProps {
  materials: CourseMaterial[]
  courseId: string
  userId: string
  onMaterialDeleted?: () => void
  materialProgress?: Record<string, { progress: number; stage: string; stageMessage: string }>
  deduplicateFlashcards?: boolean
}

export function CourseMaterialsList({ materials, courseId, userId, onMaterialDeleted, materialProgress = {}, deduplicateFlashcards = false }: CourseMaterialsListProps) {
  const [localMaterials, setLocalMaterials] = useState<CourseMaterial[]>(materials)
  const [flashcardsStatus, setFlashcardsStatus] = useState<Record<string, boolean>>({})
  const [loadingFlashcards, setLoadingFlashcards] = useState<Record<string, boolean>>({})
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [materialIdForGeneration, setMaterialIdForGeneration] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState<Record<string, boolean>>({})
  const [taskIds, setTaskIds] = useState<Record<string, string>>({})
  const [taskStatuses, setTaskStatuses] = useState<Record<string, FlashcardTaskStatus>>({})
  const [pollingIntervals, setPollingIntervals] = useState<Record<string, NodeJS.Timeout>>({})
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [materialIdForDeletion, setMaterialIdForDeletion] = useState<string | null>(null)
  const [materialNameForDeletion, setMaterialNameForDeletion] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completedMaterialId, setCompletedMaterialId] = useState<string | null>(null)
  const [completedStatus, setCompletedStatus] = useState<FlashcardTaskStatus | null>(null)
  const [isDialogDownloading, setIsDialogDownloading] = useState(false)
  const [dialogDownloadSuccess, setDialogDownloadSuccess] = useState(false)
  const startPollingRef = useRef<((materialId: string, taskId: string) => void) | null>(null)
  const handleGenerationCompleteRef = useRef<(materialId: string, status: FlashcardTaskStatus) => Promise<void> | null>(null)

  // Global background tasks context
  const backgroundTasks = useBackgroundTasksOptional()

  // Update local materials when props change
  useEffect(() => {
    setLocalMaterials(materials)
  }, [materials])

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const handleDownloadFlashcards = async (materialId: string) => {
    setLoadingFlashcards(prev => ({ ...prev, [materialId]: true }))
    try {
      const { blob, filename } = await downloadFlashcardsFromDb(materialId, userId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
      })
    } finally {
      setLoadingFlashcards(prev => ({ ...prev, [materialId]: false }))
    }
  }

  const handleGenerationComplete = useCallback(async (materialId: string, status: FlashcardTaskStatus) => {
    // Update state - generation is complete
    setIsGenerating(prev => ({ ...prev, [materialId]: false }))
    setFlashcardsStatus(prev => ({ ...prev, [materialId]: true }))
    
    // Remove from global background tasks context (it will auto-cleanup but we can be explicit)
    if (backgroundTasks) {
      backgroundTasks.updateTask(`flashcard-${materialId}`, {
        status: 'completed',
        progress: 100,
        stageMessage: `${status.cards_generated} Karten erstellt`,
      })
    }
    
    // Show completion dialog with sync status
    setCompletedMaterialId(materialId)
    setCompletedStatus(status)
    setDialogDownloadSuccess(false)
    setShowCompletionDialog(true)
  }, [backgroundTasks])

  // Keep ref updated so restore effect can call it without depending on it (avoids re-running on every context re-render)
  handleGenerationCompleteRef.current = handleGenerationComplete

  const startPolling = useCallback((materialId: string, taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await getFlashcardTaskStatus(taskId, userId)
        setTaskStatuses(prev => ({ ...prev, [materialId]: status }))

        if (status.status === 'completed') {
          clearInterval(interval)
          setPollingIntervals(prev => {
            const newIntervals = { ...prev }
            delete newIntervals[materialId]
            return newIntervals
          })
          await handleGenerationComplete(materialId, status)
        } else if (status.status === 'failed' || status.status === 'cancelled') {
          clearInterval(interval)
          setPollingIntervals(prev => {
            const newIntervals = { ...prev }
            delete newIntervals[materialId]
            return newIntervals
          })
          setIsGenerating(prev => ({ ...prev, [materialId]: false }))
          toast.error('Fehler bei der Generierung', {
            description: status.error_message || 'Die Karteikarten konnten nicht generiert werden.',
          })
        }
      } catch (error) {
        console.error('Error polling task status:', error)
        clearInterval(interval)
        setPollingIntervals(prev => {
          const newIntervals = { ...prev }
          delete newIntervals[materialId]
          return newIntervals
        })
        setIsGenerating(prev => ({ ...prev, [materialId]: false }))
        toast.error('Fehler beim Abrufen des Status', {
          description: 'Die Verbindung zum Server wurde unterbrochen.',
        })
      }
    }, 2000) // Poll every 2 seconds

    setPollingIntervals(prev => ({ ...prev, [materialId]: interval }))
  }, [userId, handleGenerationComplete])

  // Store startPolling in ref so it can be accessed in useEffect
  startPollingRef.current = startPolling

  // Initialize flashcard status from server data (instant, no API calls needed)
  useEffect(() => {
    const initialStatus: Record<string, boolean> = {}
    for (const material of localMaterials) {
      initialStatus[material.id] = material.has_flashcards ?? false
    }
    setFlashcardsStatus(initialStatus)
  }, [localMaterials])

  // Restore active flashcard generation tasks only when course page is loaded or materials/user change (e.g. reload or navigate to this course).
  // We do NOT depend on handleGenerationComplete so this effect does not re-run on every context re-render.
  useEffect(() => {
    const restoreActiveTasks = async () => {
      for (const material of localMaterials) {
        if (material.processing_status === 'completed') {
          try {
            const activeTask = await getActiveFlashcardTask(material.id, userId)
            if (activeTask) {
              setTaskIds(prev => ({ ...prev, [material.id]: activeTask.task_id }))
              setTaskStatuses(prev => ({ ...prev, [material.id]: activeTask }))
              setIsGenerating(prev => ({ ...prev, [material.id]: true }))

              if (activeTask.status === 'pending' || activeTask.status === 'running') {
                startPollingRef.current?.(material.id, activeTask.task_id)
              } else if (activeTask.status === 'completed') {
                await handleGenerationCompleteRef.current?.(material.id, activeTask)
              } else if (activeTask.status === 'failed' || activeTask.status === 'cancelled') {
                setIsGenerating(prev => ({ ...prev, [material.id]: false }))
              }
            }
          } catch (error) {
            console.error(`Error checking active task for material ${material.id}:`, error)
          }
        }
      }
    }

    if (localMaterials.length > 0) {
      restoreActiveTasks()
    }
  }, [localMaterials, userId])

  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingIntervals).forEach(interval => {
        if (interval) {
          clearInterval(interval)
        }
      })
    }
  }, [pollingIntervals])

  const handleGenerateFlashcards = async (materialId: string) => {
    setIsGenerating(prev => ({ ...prev, [materialId]: true }))
    setShowConfirmDialog(false)
    setMaterialIdForGeneration(null)

    try {
      const { task_id } = await generateFlashcards(materialId, userId, deduplicateFlashcards)
      setTaskIds(prev => ({ ...prev, [materialId]: task_id }))
      
      // Register with global background tasks context
      const material = localMaterials.find(m => m.id === materialId)
      if (backgroundTasks && material) {
        backgroundTasks.addTask({
          id: `flashcard-${materialId}`,
          type: 'flashcard_generation',
          materialId: materialId,
          materialName: material.file_name?.replace(/\.pdf$/i, '') || 'Unbekannt',
          courseId: courseId,
          progress: 0,
          status: 'running',
          stageMessage: 'Wird gestartet...',
          taskId: task_id,
        })
      }
      
      // Start polling for status
      startPolling(materialId, task_id)
      
      toast.info('Generierung gestartet', {
        description: 'Die Karteikarten werden im Hintergrund generiert.',
      })
    } catch (error) {
      console.error('Error starting flashcard generation:', error)
      toast.error('Fehler beim Starten', {
        description: error instanceof Error ? error.message : 'Die Generierung konnte nicht gestartet werden.',
      })
      setIsGenerating(prev => ({ ...prev, [materialId]: false }))
    }
  }

  const handleCancelGeneration = async (materialId: string) => {
    const taskId = taskIds[materialId]
    const interval = pollingIntervals[materialId]
    
    if (!taskId || !interval) return

    try {
      await cancelFlashcardTask(taskId, userId)
      clearInterval(interval)
      setPollingIntervals(prev => {
        const newIntervals = { ...prev }
        delete newIntervals[materialId]
        return newIntervals
      })
      setIsGenerating(prev => ({ ...prev, [materialId]: false }))
      setTaskIds(prev => {
        const newTaskIds = { ...prev }
        delete newTaskIds[materialId]
        return newTaskIds
      })
      setTaskStatuses(prev => {
        const newStatuses = { ...prev }
        delete newStatuses[materialId]
        return newStatuses
      })
      
      // Remove from global background tasks context
      if (backgroundTasks) {
        backgroundTasks.removeTask(`flashcard-${materialId}`)
      }
      
      toast.info('Generierung abgebrochen', {
        description: 'Die Karteikarten-Generierung wurde abgebrochen.',
      })
    } catch (error) {
      console.error('Error cancelling task:', error)
      toast.error('Fehler beim Abbrechen', {
        description: 'Die Generierung konnte nicht abgebrochen werden.',
      })
    }
  }

  const handleDownloadButtonClick = async (materialId: string) => {
    // Prüfe nochmal explizit, ob Flashcards existieren
    if (flashcardsStatus[materialId]) {
      // Flashcards existieren -> direkt downloaden
      handleDownloadFlashcards(materialId)
      return
    }

    // Zusätzliche Prüfung: Hole aktuelle Flashcards-Status von der API
    try {
      const result = await getFlashcardsForMaterial(materialId, userId)
      if (result.count > 0) {
        // Flashcards wurden gefunden -> Status aktualisieren und direkt downloaden
        setFlashcardsStatus(prev => ({ ...prev, [materialId]: true }))
        handleDownloadFlashcards(materialId)
        return
      }
    } catch (error) {
      // Wenn Fehler (z.B. 404), existieren keine Flashcards
      // Das ist ok, wir öffnen den Dialog
    }

    // Keine Flashcards gefunden -> Dialog öffnen
    setMaterialIdForGeneration(materialId)
    setShowConfirmDialog(true)
  }

  const getStatusBadge = (material: CourseMaterial) => {
    const status = material.processing_status
    const progress = materialProgress[material.id]
    
    switch (status) {
      case 'uploading':
        return (
          <div className="space-y-1">
            <Badge variant="outline">Wird hochgeladen</Badge>
            {progress && (
              <>
                <Progress value={progress.progress} className="h-1.5 w-24" />
                <p className="text-xs text-muted-foreground">{progress.progress}%</p>
              </>
            )}
          </div>
        )
      case 'processing':
        return (
          <div className="space-y-1 min-w-[120px]">
            <Badge variant="secondary">Wird verarbeitet</Badge>
            {progress && (
              <Progress value={progress.progress} className="h-1.5" />
            )}
          </div>
        )
      case 'completed':
        return <Badge variant="default">Abgeschlossen</Badge>
      case 'error':
        return <Badge variant="destructive">Fehler</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const handleFilenameUpdate = (materialId: string, newFilename: string) => {
    setLocalMaterials((prev) =>
      prev.map((m) => (m.id === materialId ? { ...m, file_name: newFilename } : m))
    )
  }

  const handleDeleteClick = (materialId: string, materialName: string) => {
    setMaterialIdForDeletion(materialId)
    setMaterialNameForDeletion(materialName)
    setShowDeleteDialog(true)
  }

  const handleDeleteMaterial = async () => {
    if (!materialIdForDeletion) return

    setIsDeleting(true)
    try {
      await deleteMaterial(materialIdForDeletion, userId)
      
      // Optimistically remove from UI
      setLocalMaterials((prev) => prev.filter((m) => m.id !== materialIdForDeletion))
      
      // Clean up any related state
      setFlashcardsStatus((prev) => {
        const newStatus = { ...prev }
        delete newStatus[materialIdForDeletion]
        return newStatus
      })
      setLoadingFlashcards((prev) => {
        const newStatus = { ...prev }
        delete newStatus[materialIdForDeletion]
        return newStatus
      })
      setIsGenerating((prev) => {
        const newStatus = { ...prev }
        delete newStatus[materialIdForDeletion]
        return newStatus
      })
      
      // Clear any polling intervals for this material
      if (pollingIntervals[materialIdForDeletion]) {
        clearInterval(pollingIntervals[materialIdForDeletion])
        setPollingIntervals((prev) => {
          const newIntervals = { ...prev }
          delete newIntervals[materialIdForDeletion]
          return newIntervals
        })
      }
      
      // Remove any background tasks for this material
      if (backgroundTasks) {
        // Remove by material ID (for processing tasks)
        backgroundTasks.removeTask(materialIdForDeletion)
        // Also remove flashcard tasks
        backgroundTasks.removeTask(`flashcard-${materialIdForDeletion}`)
      }
      
      toast.success('Material gelöscht', {
        description: 'Das Material wurde erfolgreich gelöscht.',
      })
      
      // Refresh parent container if callback provided
      if (onMaterialDeleted) {
        onMaterialDeleted()
      }
      
      setShowDeleteDialog(false)
      setMaterialIdForDeletion(null)
      setMaterialNameForDeletion(null)
    } catch (error) {
      console.error('Error deleting material:', error)
      toast.error('Fehler beim Löschen', {
        description: error instanceof Error ? error.message : 'Das Material konnte nicht gelöscht werden.',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDialogDownload = async () => {
    if (!completedMaterialId) return

    setIsDialogDownloading(true)
    try {
      const { blob, filename } = await downloadFlashcardsFromDb(completedMaterialId, userId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setDialogDownloadSuccess(true)
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
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
      <div className="rounded-lg border p-6">
        <p className="text-muted-foreground text-center">
          Noch keine Materialien hochgeladen.
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-lg border">
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
            {localMaterials.map((material) => (
              <TableRow key={material.id}>
                <TableCell className="font-medium">
                  <EditableFilename
                    materialId={material.id}
                    userId={userId}
                    initialFilename={material.file_name}
                    onUpdate={(newFilename) => handleFilenameUpdate(material.id, newFilename)}
                  />
                </TableCell>
                <TableCell>{material.page_count}</TableCell>
                <TableCell>{getStatusBadge(material)}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(material.created_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    {material.processing_status === 'completed' ? (
                      <>
                        <Button asChild variant="outline" size="sm">
                          <Link href={`/dashboard/courses/${courseId}/study/${material.id}`}>
                            <BookOpen className="mr-2 h-4 w-4" />
                            Studieren
                          </Link>
                        </Button>
                        <Button
                          variant="default"
                          size="sm"
                          className="text-white disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                          style={{ backgroundColor: '#B47EDE' }}
                          onMouseEnter={(e) => {
                            if (!loadingFlashcards[material.id] && !isGenerating[material.id]) {
                              e.currentTarget.style.backgroundColor = '#9d6bc9'
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!loadingFlashcards[material.id] && !isGenerating[material.id]) {
                              e.currentTarget.style.backgroundColor = '#B47EDE'
                            }
                          }}
                          disabled={loadingFlashcards[material.id] || isGenerating[material.id]}
                          onClick={() => handleDownloadButtonClick(material.id)}
                        >
                          {isGenerating[material.id] ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              {taskStatuses[material.id]?.progress !== undefined
                                ? `Wird erstellt... ${Math.round(taskStatuses[material.id].progress * 100)}%`
                                : 'Wird erstellt...'}
                            </>
                          ) : (
                            <>
                              {flashcardsStatus[material.id] ? (
                                <Download className="mr-2 h-4 w-4" />
                              ) : (
                                <Play className="mr-2 h-4 w-4" />
                              )}
                              Flashcards
                            </>
                          )}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button variant="outline" size="sm" disabled>
                          <BookOpen className="mr-2 h-4 w-4" />
                          Studieren
                        </Button>
                        <Button
                          variant="default"
                          size="sm"
                          className="text-white disabled:opacity-50 disabled:cursor-not-allowed"
                          style={{ backgroundColor: '#B47EDE' }}
                          disabled
                        >
                          <Play className="mr-2 h-4 w-4" />
                          Flashcards
                        </Button>
                      </>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0 cursor-pointer focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0 focus:ring-offset-0 focus-visible:ring-offset-0 !ring-offset-0">
                          <span className="sr-only">Mehr Optionen</span>
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-white">
                        <DropdownMenuItem
                          className="text-destructive hover:bg-destructive hover:text-destructive-foreground focus:bg-destructive focus:text-destructive-foreground cursor-pointer"
                          onClick={() => handleDeleteClick(material.id, material.file_name)}
                          disabled={isDeleting}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Löschen
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent className="bg-white">
          <DialogHeader>
            <DialogTitle>Karteikarten erstellen</DialogTitle>
            <DialogDescription>
              Bist du dir sicher, dass du die Karteikarten schon erstellen willst? Für ein optimales Ergebniss, gehe erst die Vorlesung mit deinem Tutor Agent durch.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              className="cursor-pointer"
              onClick={() => {
                setShowConfirmDialog(false)
                setMaterialIdForGeneration(null)
              }}
            >
              Abbrechen
            </Button>
            <Button
              className="cursor-pointer"
              onClick={() => {
                if (materialIdForGeneration) {
                  handleGenerateFlashcards(materialIdForGeneration)
                }
              }}
            >
              Weiter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="bg-white">
          <DialogHeader>
            <DialogTitle>Material löschen</DialogTitle>
            <DialogDescription>
              Bist du dir sicher, dass du "{materialNameForDeletion}" löschen möchtest? Diese Aktion kann nicht rückgängig gemacht werden. Alle zugehörigen Daten (Flashcards, Anki-Decks, etc.) werden ebenfalls gelöscht.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              className="cursor-pointer"
              onClick={() => {
                setShowDeleteDialog(false)
                setMaterialIdForDeletion(null)
                setMaterialNameForDeletion(null)
              }}
              disabled={isDeleting}
            >
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              className="cursor-pointer"
              onClick={handleDeleteMaterial}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Wird gelöscht...
                </>
              ) : (
                'Löschen'
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
