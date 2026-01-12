"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Calendar } from "@/components/ui/calendar"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { Calendar as CalendarIcon, Pencil } from "lucide-react"

interface ExamDateEditorProps {
  courseId: string
  userId: string
  initialDate?: string | null
}

export function ExamDateEditor({ courseId, userId, initialDate }: ExamDateEditorProps) {
  const initialDateObj = useMemo(
    () => (initialDate ? new Date(initialDate) : undefined),
    [initialDate]
  )
  const [date, setDate] = useState<Date | undefined>(initialDateObj)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const router = useRouter()

  const formattedDate = useMemo(() => {
    if (!date) return "Kein Datum gesetzt"
    return date.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    })
  }, [date])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const examDate = date ? date.toISOString().slice(0, 10) : null
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
      
      const updateResponse = await fetch(
        `${apiUrl}/api/courses/${courseId}?user_id=${userId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            exam_date: examDate,
          }),
        }
      )

      if (!updateResponse.ok) {
        const errorData = await updateResponse.json().catch(() => ({
          detail: "Update failed",
        }))
        throw new Error(errorData.detail || `Update failed: ${updateResponse.statusText}`)
      }

      router.refresh()
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-2 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Prüfungsdatum</p>
          <p className="text-lg font-semibold">{formattedDate}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Prüfungsdatum bearbeiten"
          onClick={() => setOpen(true)}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-[400px] bg-white text-foreground">
          <DialogHeader>
            <DialogTitle className="text-foreground">Prüfungsdatum wählen</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {error && (
              <div className="rounded-md bg-red-50 p-2 text-sm text-red-700">
                {error}
              </div>
            )}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarIcon className="h-4 w-4" />
              <span>Bitte wähle ein Datum aus</span>
            </div>
            <Separator />
            <Calendar
              mode="single"
              buttonVariant="outline"
              defaultMonth={date || initialDateObj}
              selected={date}
              onSelect={setDate}
              className="rounded-lg border bg-white p-3 shadow-sm min-w-[320px]"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={saving}>
              Abbrechen
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Speichert..." : "Speichern"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
