"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
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
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
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
  const [isSaving, setIsSaving] = useState(false)

  const handleDeduplicateChange = async (checked: boolean) => {
    setDeduplicateFlashcards(checked)
    setIsSaving(true)

    try {
      const { error: updateError } = await supabase
        .from("courses")
        .update({
          deduplicate_flashcards: checked,
        })
        .eq("id", courseId)
        .eq("user_id", userId)

      if (updateError) {
        throw new Error(updateError.message)
      }

      toast.success("Einstellung gespeichert")
      router.refresh()
    } catch (err) {
      // Revert on error
      setDeduplicateFlashcards(!checked)
      toast.error("Fehler beim Speichern", {
        description: err instanceof Error ? err.message : "Unbekannter Fehler",
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Settings className="h-4 w-4" />
          <span className="sr-only">Kurseinstellungen</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 bg-white">
        <DropdownMenuLabel>Kurseinstellungen</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="p-3 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label
                htmlFor="deduplicate-flashcards"
                className="text-sm font-medium cursor-pointer"
              >
                Karteikarten Deduplizierung
              </Label>
              <p className="text-xs text-muted-foreground">
                Vergleicht neue Karteikarten mit existierenden im Kurs und
                entfernt Duplikate (&gt;85% Ähnlichkeit)
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
