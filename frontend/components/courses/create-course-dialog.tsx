"use client"

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useRouter } from 'next/navigation'
import { Plus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const courseSchema = z.object({
  title: z.string().min(1, 'Titel ist erforderlich'),
  description: z.string().optional(),
  exam_date: z.string().optional(),
})

type CourseFormData = z.infer<typeof courseSchema>

interface CreateCourseDialogProps {
  userId: string
}

export function CreateCourseDialog({ userId }: CreateCourseDialogProps) {
  const [open, setOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CourseFormData>({
    resolver: zodResolver(courseSchema),
  })

  const onSubmit = async (data: CourseFormData) => {
    setIsLoading(true)
    setError(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      
      const createResponse = await fetch(
        `${apiUrl}/api/courses?user_id=${userId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: data.title,
            description: data.description || null,
            exam_date: data.exam_date || null,
          }),
        }
      )

      if (!createResponse.ok) {
        const errorData = await createResponse.json().catch(() => ({
          detail: 'Create failed',
        }))
        throw new Error(errorData.detail || `Create failed: ${createResponse.statusText}`)
      }

      const course = await createResponse.json()

      // Reset form and close dialog
      reset()
      setOpen(false)

      // Redirect to course detail page
      router.push(`/dashboard/courses/${course.id}`)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Neuer Kurs
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px] bg-white text-foreground">
        <DialogHeader>
          <DialogTitle className="text-foreground">Neuen Kurs erstellen</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Erstelle einen neuen Kurs und beginne mit dem Hochladen von Vorlesungsmaterialien.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
                {error}
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="title">Titel *</Label>
              <Input
                id="title"
                placeholder="z.B. KI Grundlagen"
                {...register('title')}
                disabled={isLoading}
              />
              {errors.title && (
                <p className="text-sm text-red-600">{errors.title.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Beschreibung</Label>
              <Input
                id="description"
                placeholder="Optionale Beschreibung des Kurses"
                {...register('description')}
                disabled={isLoading}
              />
              {errors.description && (
                <p className="text-sm text-red-600">{errors.description.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="exam_date">Prüfungsdatum</Label>
              <Input
                id="exam_date"
                type="date"
                {...register('exam_date')}
                disabled={isLoading}
              />
              {errors.exam_date && (
                <p className="text-sm text-red-600">{errors.exam_date.message}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={isLoading}>
              Abbrechen
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Erstelle...' : 'Erstellen'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
