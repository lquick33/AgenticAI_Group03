"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { Calendar as CalendarIcon, Pencil } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Separator } from "@/components/ui/separator"
import { getApiUrl } from "@/lib/public-env"

interface ExamDateEditorProps {
  courseId: string
  userId: string
  initialDate?: string | null
}

interface ExamDateFormValues {
  examDate?: Date
}

export function ExamDateEditor({ courseId, userId, initialDate }: ExamDateEditorProps) {
  const initialDateObj = useMemo(
    () => (initialDate ? new Date(initialDate) : undefined),
    [initialDate]
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const form = useForm<ExamDateFormValues>({
    defaultValues: {
      examDate: initialDateObj,
    },
  })

  useEffect(() => {
    form.reset({ examDate: initialDateObj })
  }, [form, initialDateObj])

  const selectedDate = form.watch("examDate")

  const formattedDate = useMemo(() => {
    if (!selectedDate) return "Kein Datum gesetzt"
    return selectedDate.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    })
  }, [selectedDate])

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setError(null)
      form.reset({ examDate: initialDateObj })
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)

    try {
      const examDateValue = form.getValues("examDate")
      const examDate = examDateValue ? examDateValue.toISOString().slice(0, 10) : null
      const apiUrl = getApiUrl()
      const updateResponse = await fetch(`${apiUrl}/api/courses/${courseId}?user_id=${userId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          exam_date: examDate,
        }),
      })

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
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <div className="space-y-2 rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Pruefungsdatum</p>
            <p className="text-lg font-semibold">{formattedDate}</p>
          </div>
          <DialogTrigger asChild>
            <Button variant="ghost" size="icon-touch" aria-label="Pruefungsdatum bearbeiten">
              <Pencil className="h-4 w-4" />
            </Button>
          </DialogTrigger>
        </div>
      </div>
      <DialogContent className="sm:max-w-[400px] bg-white text-foreground">
        <DialogHeader>
          <DialogTitle className="text-foreground">Pruefungsdatum waehlen</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <div className="space-y-3">
            {error && (
              <div className="rounded-md bg-red-50 p-2 text-sm text-red-700">
                {error}
              </div>
            )}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarIcon className="h-4 w-4" />
              <span>Bitte waehle ein Datum aus</span>
            </div>
            <Separator />
            <FormField
              control={form.control}
              name="examDate"
              render={({ field }) => (
                <FormItem>
                  <FormLabel className="sr-only">Pruefungsdatum</FormLabel>
                  <FormControl>
                    <Calendar
                      mode="single"
                      buttonVariant="outline"
                      defaultMonth={field.value || initialDateObj}
                      selected={field.value}
                      onSelect={field.onChange}
                      className="min-w-[320px] rounded-lg border bg-white p-3 shadow-sm"
                    />
                  </FormControl>
                  <FormDescription>Das Datum wird direkt im Kursprofil gespeichert.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </Form>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={saving}>
            Abbrechen
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Speichert..." : "Speichern"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
