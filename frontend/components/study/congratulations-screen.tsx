"use client"

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Download, Loader2, CheckCircle2, X } from 'lucide-react'
import { 
  generateFlashcards, 
  getFlashcardTaskStatus, 
  downloadFlashcards,
  cancelFlashcardTask,
  type FlashcardTaskStatus 
} from '@/lib/api/study'
import { toast } from 'sonner'
import { DeckCompletionDialog } from './deck-completion-dialog'
import { useBackgroundTasksOptional } from '@/components/background-tasks'

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
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)
  const [showCompletionDialog, setShowCompletionDialog] = useState(false)
  const [completedStatus, setCompletedStatus] = useState<FlashcardTaskStatus | null>(null)
  
  // Global background tasks context
  const backgroundTasks = useBackgroundTasksOptional()

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval)
      }
    }
  }, [pollingInterval])

  const startPolling = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await getFlashcardTaskStatus(taskId, userId)
        setTaskStatus(status)

        if (status.status === 'completed') {
          clearInterval(interval)
          setPollingInterval(null)
          setIsGenerating(false)
          setCompletedStatus(status)
          setShowCompletionDialog(true)
          
          // Update global task as completed
          if (backgroundTasks) {
            backgroundTasks.updateTask(`flashcard-${materialId}`, {
              status: 'completed',
              progress: 100,
              stageMessage: `${status.cards_generated} Karten erstellt`,
            })
          }
        } else if (status.status === 'failed' || status.status === 'cancelled') {
          clearInterval(interval)
          setPollingInterval(null)
          setIsGenerating(false)
          
          // Update global task as failed
          if (backgroundTasks) {
            backgroundTasks.updateTask(`flashcard-${materialId}`, {
              status: status.status as 'failed' | 'cancelled',
              stageMessage: status.error_message || 'Fehler aufgetreten',
            })
          }
          
          toast.error('Fehler bei der Generierung', {
            description: status.error_message || 'Die Karteikarten konnten nicht generiert werden.',
          })
        }
      } catch (error) {
        console.error('Error polling task status:', error)
        clearInterval(interval)
        setPollingInterval(null)
        setIsGenerating(false)
        toast.error('Fehler beim Abrufen des Status', {
          description: 'Die Verbindung zum Server wurde unterbrochen.',
        })
      }
    }, 2000) // Poll every 2 seconds

    setPollingInterval(interval)
  }

  const handleDownload = async () => {
    if (!taskId) return

    setIsDownloading(true)
    try {
      const { blob, filename } = await downloadFlashcards(taskId, userId)
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      setDownloadSuccess(true)
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
      })
    } finally {
      setIsDownloading(false)
    }
  }

  const handleCancel = async () => {
    if (!taskId || !pollingInterval) return

    try {
      await cancelFlashcardTask(taskId, userId)
      clearInterval(pollingInterval)
      setPollingInterval(null)
      setIsGenerating(false)
      setTaskId(null)
      setTaskStatus(null)
      
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

  const handleGenerateFlashcards = async () => {
    setIsGenerating(true)
    setDownloadSuccess(false)
    setTaskStatus(null)

    try {
      const { task_id } = await generateFlashcards(materialId, userId)
      setTaskId(task_id)
      
      // Register with global background tasks context
      if (backgroundTasks) {
        backgroundTasks.addTask({
          id: `flashcard-${materialId}`,
          type: 'flashcard_generation',
          materialId: materialId,
          materialName: materialName || 'Vorlesung',
          courseId: courseId,
          courseName: courseName,
          progress: 0,
          status: 'running',
          stageMessage: 'Wird gestartet...',
          taskId: task_id,
        })
      }
      
      // Start polling for status
      startPolling(task_id)
      
      toast.info('Generierung gestartet', {
        description: 'Die Karteikarten werden im Hintergrund generiert.',
      })
    } catch (error) {
      console.error('Error starting flashcard generation:', error)
      toast.error('Fehler beim Starten', {
        description: error instanceof Error ? error.message : 'Die Generierung konnte nicht gestartet werden.',
      })
      setIsGenerating(false)
    }
  }

  const handleCloseCompletionDialog = () => {
    setShowCompletionDialog(false)
  }

  return (
    <>
      <DeckCompletionDialog
        isOpen={showCompletionDialog}
        onClose={handleCloseCompletionDialog}
        status={completedStatus}
        onDownload={handleDownload}
        isDownloading={isDownloading}
        downloadSuccess={downloadSuccess}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
        <Card className="w-full max-w-2xl mx-4 bg-white/85">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <CheckCircle2 className="h-16 w-16 text-green-500" />
          </div>
          <CardTitle className="text-3xl">Herzlichen Glückwunsch!</CardTitle>
          <CardDescription className="text-lg mt-2">
            Du hast die Vorlesung erfolgreich durchgearbeitet.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <p className="text-center text-muted-foreground">
            Du kannst jetzt deine persönlichen Karteikarten herunterladen, die auf Basis der
            Vorlesungsinhalte und deiner Konversationen mit dem Tutor erstellt wurden.
          </p>

          <div className="flex flex-col gap-4">
            {/* Progress display */}
            {isGenerating && taskStatus && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    {taskStatus.status === 'running' 
                      ? `Seite ${taskStatus.processed_pages} von ${taskStatus.total_pages} verarbeitet...`
                      : 'Wird vorbereitet...'}
                  </span>
                  <span className="font-medium">
                    {Math.round(taskStatus.progress * 100)}%
                  </span>
                </div>
                <Progress value={taskStatus.progress * 100} className="h-2" />
                {taskStatus.cards_generated > 0 && (
                  <p className="text-xs text-muted-foreground text-center">
                    {taskStatus.cards_generated} Karteikarten generiert
                  </p>
                )}
              </div>
            )}

            <Button
              onClick={handleGenerateFlashcards}
              disabled={isGenerating || completedStatus !== null}
              size="lg"
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
              <Button
                onClick={() => setShowCompletionDialog(true)}
                variant="outline"
                size="lg"
                className="w-full"
              >
                Status anzeigen
              </Button>
            )}

            {isGenerating && taskId && (
              <Button
                onClick={handleCancel}
                variant="outline"
                size="sm"
                className="w-full"
              >
                <X className="mr-2 h-4 w-4" />
                Abbrechen
              </Button>
            )}

            {onClose && (
              <Button
                onClick={onClose}
                variant="outline"
                size="lg"
                className="w-full"
              >
                Zurück zur Vorlesung
              </Button>
            )}
          </div>

          <div className="text-sm text-center text-muted-foreground">
            <p>
              Die Karteikarten können direkt in Anki importiert werden.
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
