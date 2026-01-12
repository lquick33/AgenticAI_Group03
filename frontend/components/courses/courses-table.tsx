"use client"

import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { CourseWithStats } from '@/types'

interface CoursesTableProps {
  courses: CourseWithStats[]
}

export function CoursesTable({ courses }: CoursesTableProps) {
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Nie'
    const date = new Date(dateString)
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  const calculateProgress = (analyzedPages: number, totalPages: number) => {
    if (totalPages === 0) return 0
    return Math.round((analyzedPages / totalPages) * 100)
  }

  if (courses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Noch keine Kurse vorhanden.</p>
        <p className="text-sm text-muted-foreground mt-2">
          Erstelle deinen ersten Kurs, um zu beginnen.
        </p>
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Titel</TableHead>
          <TableHead>Beschreibung</TableHead>
          <TableHead>Materialien</TableHead>
          <TableHead>Progress</TableHead>
          <TableHead>Letztes Update</TableHead>
          <TableHead className="text-right">Aktionen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {courses.map((course) => {
          const progress = calculateProgress(course.analyzed_pages, course.total_pages)
          return (
            <TableRow key={course.id} className="cursor-pointer hover:bg-muted/50">
              <TableCell className="font-medium">{course.title}</TableCell>
              <TableCell className="text-muted-foreground">
                {course.description || '-'}
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{course.material_count}</Badge>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="flex-1 min-w-[100px]">
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-sm text-muted-foreground min-w-[45px]">
                    {progress}%
                  </span>
                </div>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDate(course.last_updated)}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/dashboard/courses/${course.id}`}>
                  <Button variant="ghost" size="sm">
                    Öffnen
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
