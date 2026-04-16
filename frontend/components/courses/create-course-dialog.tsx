"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Plus } from "lucide-react"
import * as z from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { getApiUrl } from "@/lib/public-env"

const courseSchema = z.object({
  title: z.string().min(1, "Titel ist erforderlich"),
  description: z.string().optional(),
  exam_date: z.string().optional(),
})

type CourseFormData = z.infer<typeof courseSchema>

interface CreateCourseDialogProps {
  userId: string
}

const defaultValues: CourseFormData = {
  title: "",
  description: "",
  exam_date: "",
}

export function CreateCourseDialog({ userId }: CreateCourseDialogProps) {
  const [open, setOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const form = useForm<CourseFormData>({
    resolver: zodResolver(courseSchema),
    defaultValues,
  })

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setError(null)
      form.reset(defaultValues)
    }
  }

  const onSubmit = async (data: CourseFormData) => {
    setIsLoading(true)
    setError(null)

    try {
      const apiUrl = getApiUrl()
      const createResponse = await fetch(`${apiUrl}/api/courses?user_id=${userId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: data.title,
          description: data.description || null,
          exam_date: data.exam_date || null,
        }),
      })

      if (!createResponse.ok) {
        const errorData = await createResponse.json().catch(() => ({
          detail: "Create failed",
        }))
        throw new Error(errorData.detail || `Create failed: ${createResponse.statusText}`)
      }

      const course = await createResponse.json()
      form.reset(defaultValues)
      setOpen(false)
      router.push(`/dashboard/courses/${course.id}`)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
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
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
                {error}
              </div>
            )}

            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Titel *</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="z.B. KI Grundlagen"
                      disabled={isLoading}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Beschreibung</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Optionale Beschreibung des Kurses"
                      disabled={isLoading}
                      value={field.value ?? ""}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      name={field.name}
                      ref={field.ref}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="exam_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Pruefungsdatum</FormLabel>
                  <FormControl>
                    <Input
                      type="date"
                      disabled={isLoading}
                      value={field.value ?? ""}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      name={field.name}
                      ref={field.ref}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isLoading}>
                Abbrechen
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? "Erstelle..." : "Erstellen"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
