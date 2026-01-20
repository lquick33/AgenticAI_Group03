"use client"

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { BookOpen, Download } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { CourseMaterial } from '@/types'
import { getFlashcardsForMaterial, downloadFlashcardsFromDb } from '@/lib/api/study'
import { toast } from 'sonner'

interface CourseMaterialsListProps {
  materials: CourseMaterial[]
  courseId: string
  userId: string
}

export function CourseMaterialsList({ materials, courseId, userId }: CourseMaterialsListProps) {
  const [flashcardsStatus, setFlashcardsStatus] = useState<Record<string, boolean>>({})
  const [loadingFlashcards, setLoadingFlashcards] = useState<Record<string, boolean>>({})

  // Check flashcards availability for all materials
  useEffect(() => {
    const checkFlashcards = async () => {
      const status: Record<string, boolean> = {}
      for (const material of materials) {
        if (material.processing_status === 'completed') {
          try {
            const result = await getFlashcardsForMaterial(material.id, userId)
            status[material.id] = result.count > 0
          } catch (error) {
            // If error (e.g., 404), no flashcards exist
            status[material.id] = false
          }
        } else {
          status[material.id] = false
        }
      }
      setFlashcardsStatus(status)
    }

    if (materials.length > 0) {
      checkFlashcards()
    }
  }, [materials, userId])

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const handleDownloadFlashcards = async (materialId: string) => {
    setLoadingFlashcards(prev => ({ ...prev, [materialId]: true }))
    try {
      const blob = await downloadFlashcardsFromDb(materialId, userId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `flashcards_${materialId}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success('Flashcards heruntergeladen', {
        description: 'Die Karteikarten wurden erfolgreich heruntergeladen.',
      })
    } catch (error) {
      console.error('Error downloading flashcards:', error)
      toast.error('Fehler beim Download', {
        description: error instanceof Error ? error.message : 'Die Karteikarten konnten nicht heruntergeladen werden.',
      })
    } finally {
      setLoadingFlashcards(prev => ({ ...prev, [materialId]: false }))
    }
  }

  const getStatusBadge = (status: CourseMaterial['processing_status']) => {
    switch (status) {
      case 'uploading':
        return <Badge variant="outline">Wird hochgeladen</Badge>
      case 'processing':
        return <Badge variant="secondary">Wird verarbeitet</Badge>
      case 'completed':
        return <Badge variant="default">Abgeschlossen</Badge>
      case 'error':
        return <Badge variant="destructive">Fehler</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  if (materials.length === 0) {
    return (
      <div className="rounded-lg border p-6">
        <p className="text-muted-foreground text-center">
          Noch keine Materialien hochgeladen.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Dateiname</TableHead>
            <TableHead>Seiten</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Hochgeladen am</TableHead>
            <TableHead className="text-right">Aktionen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {materials.map((material) => (
            <TableRow key={material.id}>
              <TableCell className="font-medium">{material.file_name}</TableCell>
              <TableCell>{material.page_count}</TableCell>
              <TableCell>{getStatusBadge(material.processing_status)}</TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(material.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-2">
                  {material.processing_status === 'completed' ? (
                    <>
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/dashboard/courses/${courseId}/study/${material.id}`}>
                          <BookOpen className="mr-2 h-4 w-4" />
                          Studieren
                        </Link>
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-black text-white hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={!flashcardsStatus[material.id] || loadingFlashcards[material.id]}
                        onClick={() => handleDownloadFlashcards(material.id)}
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" disabled>
                        <BookOpen className="mr-2 h-4 w-4" />
                        Studieren
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        className="bg-black text-white hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download
                      </Button>
                    </>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
