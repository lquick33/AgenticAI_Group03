"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation } from "@tanstack/react-query"
import { Settings } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { createClient } from "@/lib/supabase/client"

interface CourseSettingsProps {
  courseId: string
  userId: string
  initialDeduplicateFlashcards?: boolean
}

export function CourseSettings({
  courseId,
  userId,
  initialDeduplicateFlashcards = false,
}: CourseSettingsProps) {
  const router = useRouter()
  const supabase = createClient()
  const [deduplicateFlashcards, setDeduplicateFlashcards] = useState(
    initialDeduplicateFlashcards
  )

  const { mutate, isPending: isSaving } = useMutation({
    mutationFn: async (checked: boolean) => {
      const { error: updateError } = await supabase
        .from("courses")
        .update({ deduplicate_flashcards: checked })
        .eq("id", courseId)
        .eq("user_id", userId)

      if (updateError) throw new Error(updateError.message)
      return checked
    },
    onSuccess: () => {
      toast.success("Einstellung gespeichert")
      router.refresh()
    },
    onError: (err, checked) => {
      setDeduplicateFlashcards(!checked)
      toast.error("Fehler beim Speichern", {
        description: err.message || "Unbekannter Fehler",
      })
    }
  })

  const handleDeduplicateChange = (checked: boolean) => {
    setDeduplicateFlashcards(checked)
    mutate(checked)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon-touch" aria-label="Kurseinstellungen oeffnen">
          <Settings className="h-4 w-4" />
          <span className="sr-only">Kurseinstellungen</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Kurseinstellungen</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="space-y-4 p-4">
          <div className="flex items-start justify-between gap-4 rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] p-4">
            <div className="space-y-1.5 pr-2">
              <Label
                htmlFor="deduplicate-flashcards"
                className="cursor-pointer text-sm font-medium"
              >
                Karteikarten deduplizieren
              </Label>
              <p className="text-xs leading-5 text-muted-foreground">
                Vergleicht neue Karteikarten mit bestehenden Karten im Kurs und entfernt sehr aehnliche Duplikate automatisch.
              </p>
            </div>
            <Switch
              id="deduplicate-flashcards"
              checked={deduplicateFlashcards}
              onCheckedChange={handleDeduplicateChange}
              disabled={isSaving}
            />
          </div>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
