"use client"

import { useState } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useRouter } from 'next/navigation'

interface UploadSectionProps {
  courseId: string
  userId: string
}

export function UploadSection({ courseId, userId }: UploadSectionProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const router = useRouter()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.type !== 'application/pdf') {
        setError('Bitte wähle eine PDF-Datei aus')
        return
      }
      setSelectedFile(file)
      setError(null)
      setSuccess(false)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Bitte wähle eine Datei aus')
      return
    }

    setIsUploading(true)
    setError(null)
    setSuccess(false)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('user_id', userId)
      formData.append('course_id', courseId)

      const response = await fetch(`${apiUrl}/api/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(errorData.detail || `Upload failed: ${response.statusText}`)
      }

      const result = await response.json()
      setSuccess(true)
      setSelectedFile(null)
      
      // Reset file input
      const fileInput = document.getElementById('file-upload') as HTMLInputElement
      if (fileInput) {
        fileInput.value = ''
      }

      // Refresh the page to show new material
      setTimeout(() => {
        router.refresh()
        setSuccess(false)
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-6">
        <h3 className="text-lg font-semibold mb-4">Vorlesungsmaterial hochladen</h3>
        
        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-800 mb-4">
            {error}
          </div>
        )}
        
        {success && (
          <div className="rounded-md bg-green-50 p-3 text-sm text-green-800 mb-4">
            Datei erfolgreich hochgeladen! Die Verarbeitung läuft im Hintergrund.
          </div>
        )}

        <div className="flex flex-col gap-4">
          <div>
            <label
              htmlFor="file-upload"
              className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-muted-foreground/25 rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
                <p className="mb-2 text-sm text-muted-foreground">
                  <span className="font-semibold">Klicke zum Hochladen</span> oder ziehe die Datei hierher
                </p>
                <p className="text-xs text-muted-foreground">PDF (max. 50MB)</p>
              </div>
              <input
                id="file-upload"
                type="file"
                className="hidden"
                accept=".pdf"
                onChange={handleFileChange}
                disabled={isUploading}
              />
            </label>
            {selectedFile && (
              <p className="mt-2 text-sm text-muted-foreground">
                Ausgewählte Datei: {selectedFile.name}
              </p>
            )}
          </div>

          <Button
            onClick={handleUpload}
            disabled={!selectedFile || isUploading}
            className="w-full"
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Wird hochgeladen...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Hochladen
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
