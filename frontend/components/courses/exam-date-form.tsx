"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useMutation } from "@tanstack/react-query"
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
  const [success, setSuccess] = useState(false)

  const { mutate, isPending: isSaving, error } = useMutation({
    mutationFn: async (date: string) => {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) throw new Error("User not authenticated")

      const { error: updateError } = await supabase
        .from("courses")
        .update({ exam_date: date || null })
        .eq("id", courseId)
        .eq("user_id", user.id)

      if (updateError) throw new Error(updateError.message)
      return date
    },
    onSuccess: () => {
      setSuccess(true)
      router.refresh()
    }
  })

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [success])

  const handleSave = () => {
    mutate(examDate)
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
      {error && <p className="text-sm text-red-600">{error.message || "Konnte Prüfungsdatum nicht speichern"}</p>}
      {success && <p className="text-sm text-green-600">Gespeichert</p>}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Speichert..." : "Speichern"}
        </Button>
      </div>
    </div>
  )
}
