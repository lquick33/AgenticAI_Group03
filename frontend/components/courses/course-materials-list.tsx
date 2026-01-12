"use client"

import Link from 'next/link'
import { BookOpen } from 'lucide-react'
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

interface CourseMaterialsListProps {
  materials: CourseMaterial[]
  courseId: string
}

export function CourseMaterialsList({ materials, courseId }: CourseMaterialsListProps) {
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
                {material.processing_status === 'completed' ? (
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/dashboard/courses/${courseId}/study/${material.id}`}>
                      <BookOpen className="mr-2 h-4 w-4" />
                      Studieren
                    </Link>
                  </Button>
                ) : (
                  <Button variant="outline" size="sm" disabled>
                    <BookOpen className="mr-2 h-4 w-4" />
                    Studieren
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
