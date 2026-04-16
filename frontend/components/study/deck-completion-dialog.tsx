"use client"

import { CheckCircle2, Download, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { FlashcardTaskStatus } from "@/lib/api/study"

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

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md rounded-[1.75rem] border-[var(--app-border-soft)] bg-[var(--app-surface)] p-6 shadow-[var(--app-shadow-panel)]">
        <DialogHeader className="items-center text-center sm:items-center sm:text-center">
          <div className="mb-2 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
            <CheckCircle2 className="h-8 w-8" />
          </div>
          <DialogTitle className="text-xl">Karteikarten erstellt</DialogTitle>
          <DialogDescription className="max-w-sm text-sm leading-6">
            {status.cards_generated} Karteikarten wurden erfolgreich generiert und koennen jetzt direkt in Anki importiert werden.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] px-4 py-3 text-sm text-muted-foreground">
          Die heruntergeladene <code>.apkg</code>-Datei kannst du direkt in Anki Desktop importieren.
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          {onDownload ? (
            <Button
              onClick={onDownload}
              disabled={isDownloading || downloadSuccess}
              variant="accent"
              className="w-full"
            >
              {isDownloading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Wird heruntergeladen...
                </>
              ) : downloadSuccess ? (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  Heruntergeladen
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  .apkg herunterladen
                </>
              )}
            </Button>
          ) : null}

          <Button onClick={onClose} variant="outline" className="w-full">
            Schliessen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
