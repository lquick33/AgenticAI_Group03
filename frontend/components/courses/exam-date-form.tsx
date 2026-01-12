"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { createClient } from "@/lib/supabase/client"

interface ExamDateFormProps {
  courseId: string
  currentExamDate: string | null
}

export function ExamDateForm({ courseId, currentExamDate }: ExamDateFormProps) {
  const router = useRouter()
  const supabase = createClient()

  const [examDate, setExamDate] = useState<string>(currentExamDate ?? "")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const {
        data: { user },
      } = await supabase.auth.getUser()

      if (!user) {
        throw new Error("User not authenticated")
      }

      const { error: updateError } = await supabase
        .from("courses")
        .update({
          exam_date: examDate || null,
        })
        .eq("id", courseId)
        .eq("user_id", user.id)

      if (updateError) {
        throw new Error(updateError.message)
      }

      setSuccess(true)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Konnte Prüfungsdatum nicht speichern")
    } finally {
      setIsSaving(false)
      setTimeout(() => setSuccess(false), 2000)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2">
        <label htmlFor="exam-date" className="text-sm font-medium">
          Prüfungsdatum
        </label>
        <Input
          id="exam-date"
          type="date"
          value={examDate}
          onChange={(e) => setExamDate(e.target.value)}
          disabled={isSaving}
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-600">Gespeichert</p>}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Speichert..." : "Speichern"}
        </Button>
      </div>
    </div>
  )
}
