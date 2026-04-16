"use client"

import React from "react"
import Link from "next/link"
import { ArrowRight } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { CourseWithStats } from "@/types"

const formatDate = (dateString: string | null) => {
  if (!dateString) return "Nie"
  const date = new Date(dateString)
  return date.toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

const calculateProgress = (analyzedPages: number, totalPages: number) => {
  if (totalPages === 0) return 0
  return Math.round((analyzedPages / totalPages) * 100)
}

interface CoursesTableProps {
  courses: CourseWithStats[]
}

export const CoursesTable = React.memo(function CoursesTable({ courses }: CoursesTableProps) {
  if (courses.length === 0) {
    return (
      <div className="app-empty-state">
        <p className="text-base font-medium text-foreground">Noch keine Kurse vorhanden.</p>
        <p className="max-w-md text-sm text-muted-foreground">
          Erstelle deinen ersten Kurs, um Materialien hochzuladen und einen Lernraum aufzubauen.
        </p>
      </div>
    )
  }

  return (
    <div className="app-table-shell">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Titel</TableHead>
            <TableHead>Beschreibung</TableHead>
            <TableHead>Materialien</TableHead>
            <TableHead>Fortschritt</TableHead>
            <TableHead>Letztes Update</TableHead>
            <TableHead className="text-right">Aktionen</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {courses.map((course) => {
            const progress = calculateProgress(course.analyzed_pages, course.total_pages)
            const description = course.description?.trim() || "Noch keine Beschreibung hinterlegt."

            return (
              <TableRow key={course.id}>
                <TableCell className="min-w-[220px] align-top">
                  <div className="space-y-1">
                    <p className="font-medium text-foreground">{course.title}</p>
                    <p className="text-xs text-muted-foreground">{course.total_pages} Seiten im Kursraum</p>
                  </div>
                </TableCell>
                <TableCell className="max-w-[320px] align-top text-sm text-muted-foreground">
                  <p className="line-clamp-2">{description}</p>
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant="info">{course.material_count} Dateien</Badge>
                </TableCell>
                <TableCell className="min-w-[200px] align-top">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-muted-foreground">
                        {course.analyzed_pages} von {course.total_pages || 0} Seiten
                      </span>
                      <span className="font-medium text-foreground">{progress}%</span>
                    </div>
                    <Progress value={progress} className="h-2" />
                  </div>
                </TableCell>
                <TableCell className="align-top text-sm text-muted-foreground">
                  {formatDate(course.last_updated)}
                </TableCell>
                <TableCell className="align-top text-right">
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/dashboard/courses/${course.id}`}>
                      Oeffnen
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
})
