"use client"

import { useState, useTransition } from "react"
import { format } from "date-fns"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { createClient } from "@/lib/supabase/client"

interface ExamDatePickerProps {
  courseId: string
  initialDate?: string | null
}

export function ExamDatePicker({ courseId, initialDate }: ExamDatePickerProps) {
  const router = useRouter()
  const supabase = createClient()
  const [selected, setSelected] = useState<Date | undefined>(
    initialDate ? new Date(initialDate) : undefined
  )
  const [message, setMessage] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const handleSave = () => {
    startTransition(async () => {
      setMessage(null)
      const dateString = selected ? format(selected, "yyyy-MM-dd") : null

      const { error } = await supabase
        .from("courses")
        .update({ exam_date: dateString })
        .eq("id", courseId)

      if (error) {
        setMessage(error.message || "Fehler beim Speichern")
        return
      }

      setMessage("Prüfungsdatum gespeichert")
      router.refresh()
    })
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border p-4">
        <div className="mb-3">
          <p className="text-sm font-medium">Prüfungsdatum anpassen</p>
          <p className="text-xs text-muted-foreground">
            Wähle ein Datum aus und speichere es für diesen Kurs.
          </p>
        </div>
        <Calendar
          mode="single"
          selected={selected}
          onSelect={setSelected}
          className="rounded-lg border"
        />
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={handleSave} disabled={isPending}>
            {isPending ? "Speichert..." : "Speichern"}
          </Button>
          <Button
            variant="outline"
            onClick={() => setSelected(undefined)}
            disabled={isPending}
          >
            Datum zurücksetzen
          </Button>
        </div>
        {message && (
          <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        )}
      </div>
    </div>
  )
}
