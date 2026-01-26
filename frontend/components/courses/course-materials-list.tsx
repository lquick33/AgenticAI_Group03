"use client"

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { BookOpen, Download, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { toast } from 'sonner'

interface CourseMaterialsListProps {
  materials: CourseMaterial[]
  courseId: string
  userId: string
}

export function CourseMaterialsList({ materials, courseId, userId }: CourseMaterialsListProps) {
  const [localMaterials, setLocalMaterials] = useState<CourseMaterial[]>(materials)
  const [flashcardsStatus, setFlashcardsStatus] = useState<Record<string, boolean>>({})
  const [loadingFlashcards, setLoadingFlashcards] = useState<Record<string, boolean>>({})
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [materialIdForGeneration, setMaterialIdForGeneration] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState<Record<string, boolean>>({})
  const [taskIds, setTaskIds] = useState<Record<string, string>>({})
  const [taskStatuses, setTaskStatuses] = useState<Record<string, FlashcardTaskStatus>>({})
  const [pollingIntervals, setPollingIntervals] = useState<Record<string, NodeJS.Timeout>>({})
  const startPollingRef = useRef<((materialId: string, taskId: string) => void) | null>(null)

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
      const blob = await downloadFlashcardsFromDb(materialId, userId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `flashcards_${materialId}.apkg`
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

  const handleDownloadAfterGeneration = useCallback(async (materialId: string, status: FlashcardTaskStatus) => {
    // Use task_id from status, or get from state
    const taskId = status.task_id
    
    if (!taskId) {
      console.error('No task ID available for download')
      setIsGenerating(prev => ({ ...prev, [materialId]: false }))
      return
    }

    try {
      const blob = await downloadFlashcards(taskId, userId)
      
      // Get filename from status or use default
      const filename = status.filename || `flashcards_${materialId}.apkg`
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      setIsGenerating(prev => ({ ...prev, [materialId]: false }))
      setFlashcardsStatus(prev => ({ ...prev, [materialId]: true }))
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich generiert und heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
      })
      setIsGenerating(prev => ({ ...prev, [materialId]: false }))
    }
  }, [userId])

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
          await handleDownloadAfterGeneration(materialId, status)
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
  }, [userId, handleDownloadAfterGeneration])

  // Store startPolling in ref so it can be accessed in useEffect
  startPollingRef.current = startPolling

  // Check flashcards availability for all materials and restore active tasks
  useEffect(() => {
    const checkFlashcardsAndActiveTasks = async () => {
      const status: Record<string, boolean> = {}
      
      for (const material of localMaterials) {
        if (material.processing_status === 'completed') {
          // Check for flashcards
          try {
            const result = await getFlashcardsForMaterial(material.id, userId)
            status[material.id] = result.count > 0
          } catch (error) {
            // If error (e.g., 404), no flashcards exist
            status[material.id] = false
          }
          
          // Check for active flashcard generation task
          try {
            const activeTask = await getActiveFlashcardTask(material.id, userId)
            if (activeTask) {
              // Restore task state
              setTaskIds(prev => ({ ...prev, [material.id]: activeTask.task_id }))
              setTaskStatuses(prev => ({ ...prev, [material.id]: activeTask }))
              setIsGenerating(prev => ({ ...prev, [material.id]: true }))
              
              // Resume polling if task is still running
              if (activeTask.status === 'pending' || activeTask.status === 'running') {
                startPollingRef.current?.(material.id, activeTask.task_id)
              } else if (activeTask.status === 'completed') {
                // Task completed but we just loaded - download automatically
                await handleDownloadAfterGeneration(material.id, activeTask)
              } else if (activeTask.status === 'failed' || activeTask.status === 'cancelled') {
                // Task failed or was cancelled - reset state
                setIsGenerating(prev => ({ ...prev, [material.id]: false }))
              }
            }
          } catch (error) {
            // If error checking for active task, just continue
            console.error(`Error checking active task for material ${material.id}:`, error)
          }
        } else {
          status[material.id] = false
        }
      }
      setFlashcardsStatus(status)
    }

    if (localMaterials.length > 0) {
      checkFlashcardsAndActiveTasks()
    }
  }, [localMaterials, userId, handleDownloadAfterGeneration])

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
      const { task_id } = await generateFlashcards(materialId, userId)
      setTaskIds(prev => ({ ...prev, [materialId]: task_id }))
      
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

  const getStatusBadge = (status: CourseMaterial['processing_status']) => {
    switch (status) {
      case 'uploading':
        return <Badge variant="outline">Wird hochgeladen</Badge>
      case 'processing':
        return <Badge variant="secondary">Wird verarbeitet</Badge>
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
                <TableCell>{getStatusBadge(material.processing_status)}</TableCell>
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
                          className="text-white disabled:opacity-50 disabled:cursor-not-allowed"
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
                              <Download className="mr-2 h-4 w-4" />
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
                          <Download className="mr-2 h-4 w-4" />
                          Flashcards
                        </Button>
                      </>
                    )}
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
              onClick={() => {
                setShowConfirmDialog(false)
                setMaterialIdForGeneration(null)
              }}
            >
              Abbrechen
            </Button>
            <Button
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
    </>
  )
}
