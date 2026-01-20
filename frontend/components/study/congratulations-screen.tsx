"use client"

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Download, Loader2, CheckCircle2 } from 'lucide-react'
import { exportFlashcards } from '@/lib/api/study'
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
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadSuccess, setDownloadSuccess] = useState(false)

  const handleDownloadFlashcards = async () => {
    setIsDownloading(true)
    setDownloadSuccess(false)

    try {
      const blob = await exportFlashcards(materialId, userId)
      
      // Get filename from Content-Disposition header or use default
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `flashcards_${materialId}.csv`
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
            <Button
              onClick={handleDownloadFlashcards}
              disabled={isDownloading || downloadSuccess}
              size="lg"
              className="w-full"
            >
              {isDownloading ? (
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
                  Flashcards runterladen
                </>
              )}
            </Button>

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
