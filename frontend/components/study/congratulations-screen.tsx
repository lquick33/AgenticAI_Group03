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

interface CongratulationsScreenProps {
  materialId: string
  courseId: string
  userId: string
  onClose?: () => void
}

export function CongratulationsScreen({
  materialId,
  courseId,
  userId,
  onClose,
}: CongratulationsScreenProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [downloadSuccess, setDownloadSuccess] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [taskStatus, setTaskStatus] = useState<FlashcardTaskStatus | null>(null)
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

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
          await handleDownload(status)
        } else if (status.status === 'failed' || status.status === 'cancelled') {
          clearInterval(interval)
          setPollingInterval(null)
          setIsGenerating(false)
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

  const handleDownload = async (status: FlashcardTaskStatus) => {
    if (!taskId) return

    try {
      const blob = await downloadFlashcards(taskId, userId)
      
      // Get filename from status or use default
      const filename = status.filename || `flashcards_${materialId}.csv`
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)

      setDownloadSuccess(true)
      setIsGenerating(false)
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
      })
      setIsGenerating(false)
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <Card className="w-full max-w-2xl mx-4">
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
              disabled={isGenerating || downloadSuccess}
              size="lg"
              className="w-full"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Karteikarten werden erstellt...
                </>
              ) : downloadSuccess ? (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Erfolgreich heruntergeladen
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Flashcards erstellen
                </>
              )}
            </Button>

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
              Format: CSV mit Spalten: front, back, tags
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
