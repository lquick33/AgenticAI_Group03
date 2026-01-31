"use client"

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogPortal,
  DialogOverlay,
} from '@/components/ui/dialog'
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { CheckCircle2, CloudOff, Download, Loader2, X } from 'lucide-react'
import type { FlashcardTaskStatus } from '@/lib/api/study'

interface DeckCompletionDialogProps {
  isOpen: boolean
  onClose: () => void
  status: FlashcardTaskStatus | null
  onDownload?: () => void
  isDownloading?: boolean
  downloadSuccess?: boolean
}

export function DeckCompletionDialog({
  isOpen,
  onClose,
  status,
  onDownload,
  isDownloading = false,
  downloadSuccess = false,
}: DeckCompletionDialogProps) {
  if (!status) return null

  const getAnkiSyncStatus = () => {
    if (status.anki_synced) {
      // Both local Anki and AnkiWeb synced cases - user just needs to sync in Anki app
      return {
        icon: <CheckCircle2 className="h-5 w-5 text-green-500" />,
        text: 'Zu Anki hinzugefügt',
        description: 'Öffne Anki und synchronisiere, um die Karten auf allen Geräten zu sehen.',
        color: 'text-green-600',
      }
    } else {
      return {
        icon: <CloudOff className="h-5 w-5 text-orange-500" />,
        text: 'Manueller Import erforderlich',
        description: 'Verbinde Anki für automatischen Sync oder lade die .apkg-Datei herunter.',
        color: 'text-orange-600',
      }
    }
  }

  const syncStatus = getAnkiSyncStatus()

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay className="z-[60]" />
        <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-[60] grid w-full max-w-md translate-x-[-50%] translate-y-[-50%] gap-4 border bg-white p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg">
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground cursor-pointer">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        <DialogHeader className="text-center sm:text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-green-100 p-3">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
          </div>
          <DialogTitle className="text-xl">
            Karteikarten erstellt!
          </DialogTitle>
          <DialogDescription className="text-base">
            {status.cards_generated} Karteikarten wurden erfolgreich generiert.
          </DialogDescription>
        </DialogHeader>

        {/* Sync Status Section */}
        <div className="space-y-4 py-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-start gap-3">
              {syncStatus.icon}
              <div className="flex-1">
                <h4 className={`font-medium ${syncStatus.color}`}>
                  {syncStatus.text}
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  {syncStatus.description}
                </p>
              </div>
            </div>
          </div>


          {/* Show download option when not synced to Anki */}
          {!status.anki_synced && onDownload && (
            <div className="text-center text-sm text-muted-foreground">
              <p>
                Die .apkg-Datei kann direkt in Anki importiert werden.
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          {/* Primary close button when synced to Anki */}
          {status.anki_synced && (
            <Button
              onClick={onClose}
              className="w-full"
            >
              Schließen
            </Button>
          )}

          {/* Primary download button only when NOT synced to Anki */}
          {!status.anki_synced && onDownload && (
            <Button
              onClick={onDownload}
              disabled={isDownloading || downloadSuccess}
              className="w-full"
            >
              {isDownloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Wird heruntergeladen...
                </>
              ) : downloadSuccess ? (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Heruntergeladen
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  .apkg herunterladen
                </>
              )}
            </Button>
          )}

          {/* Secondary close button when NOT synced */}
          {!status.anki_synced && (
            <Button
              onClick={onClose}
              variant="ghost"
              className="w-full"
            >
              Schließen
            </Button>
          )}
        </DialogFooter>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  )
}
