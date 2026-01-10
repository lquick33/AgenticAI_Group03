'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Upload, Loader2, Plus } from 'lucide-react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { createClient } from '@/lib/supabase/client'
import type { Course } from '@/types'

interface UploadDialogProps {
  courses: Course[]
}

interface CourseFormData {
  title: string
  description?: string
  exam_date?: string
}

export function UploadDialog({ courses }: UploadDialogProps) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'select' | 'create'>('select')
  const [selectedCourseId, setSelectedCourseId] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CourseFormData>()

  const supabase = createClient()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.type !== 'application/pdf') {
        setError('Please select a PDF file')
        return
      }
      setSelectedFile(file)
      setError(null)
    }
  }

  const createCourse = async (data: CourseFormData) => {
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      throw new Error('User not authenticated')
    }

    const { data: course, error: courseError } = await supabase
      .from('courses')
      .insert({
        user_id: user.id,
        title: data.title,
        description: data.description || null,
        exam_date: data.exam_date || null,
      })
      .select()
      .single()

    if (courseError) {
      throw new Error(`Failed to create course: ${courseError.message}`)
    }

    return course.id
  }

  const uploadFile = async (courseId: string, file: File) => {
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      throw new Error('User not authenticated')
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', user.id)
    formData.append('course_id', courseId)

    const response = await fetch(`${apiUrl}/api/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
      throw new Error(errorData.detail || `Upload failed: ${response.statusText}`)
    }

    return await response.json()
  }

  const onSubmit = async (data: CourseFormData) => {
    if (!selectedFile) {
      setError('Please select a PDF file')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccess(false)

    try {
      let courseId = selectedCourseId

      // Create new course if in create mode
      if (mode === 'create') {
        courseId = await createCourse(data)
      }

      if (!courseId) {
        throw new Error('No course selected')
      }

      // Upload file
      await uploadFile(courseId, selectedFile)

      setSuccess(true)
      reset()
      setSelectedFile(null)
      setSelectedCourseId('')

      // Close dialog after a short delay
      setTimeout(() => {
        setOpen(false)
        setSuccess(false)
        // Reload page to show new course/material
        window.location.reload()
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsUploading(false)
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!isUploading) {
      setOpen(newOpen)
      if (!newOpen) {
        // Reset form when closing
        reset()
        setSelectedFile(null)
        setSelectedCourseId('')
        setError(null)
        setSuccess(false)
        setMode('select')
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Upload Material
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Course Material</DialogTitle>
          <DialogDescription>
            Create a new course or select an existing one, then upload a PDF file.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Mode Selection */}
          <div className="space-y-2">
            <Label>Course</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={mode === 'select' ? 'default' : 'outline'}
                onClick={() => setMode('select')}
                className="flex-1"
              >
                Select Existing
              </Button>
              <Button
                type="button"
                variant={mode === 'create' ? 'default' : 'outline'}
                onClick={() => setMode('create')}
                className="flex-1"
              >
                Create New
              </Button>
            </div>
          </div>

          {/* Select Existing Course */}
          {mode === 'select' && (
            <div className="space-y-2">
              <Label htmlFor="course-select">Select Course</Label>
              <Select
                value={selectedCourseId}
                onValueChange={setSelectedCourseId}
                required
              >
                <SelectTrigger id="course-select">
                  <SelectValue placeholder="Choose a course" />
                </SelectTrigger>
                <SelectContent>
                  {courses.length === 0 ? (
                    <SelectItem value="" disabled>
                      No courses available
                    </SelectItem>
                  ) : (
                    courses.map((course) => (
                      <SelectItem key={course.id} value={course.id}>
                        {course.title}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Create New Course */}
          {mode === 'create' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Course Title *</Label>
                <Input
                  id="title"
                  {...register('title', { required: 'Course title is required' })}
                  placeholder="e.g., Marketing 101"
                />
                {errors.title && (
                  <p className="text-sm text-red-600">{errors.title.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  {...register('description')}
                  placeholder="Optional course description"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="exam_date">Exam Date</Label>
                <Input
                  id="exam_date"
                  type="date"
                  {...register('exam_date')}
                />
              </div>
            </div>
          )}

          {/* File Upload */}
          <div className="space-y-2">
            <Label htmlFor="file">PDF File *</Label>
            <Input
              id="file"
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              disabled={isUploading}
              required
            />
            {selectedFile && (
              <p className="text-sm text-slate-600">
                Selected: {selectedFile.name}
              </p>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
              {error}
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
              Upload successful! Processing will begin shortly.
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isUploading || !selectedFile}>
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
