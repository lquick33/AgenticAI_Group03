"use client"

import * as React from "react"
import { format } from "date-fns"
import {
  CheckCircle2Icon,
  LoaderIcon,
  MoreVerticalIcon,
} from "lucide-react"
import type { LearningUnit } from "@/types"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

// Dummy data based on LearningUnit type
const dummyLearningUnits: Array<LearningUnit & { course_name: string; progress: number }> = [
  {
    id: "1",
    course_id: "course-1",
    topic_name: "Einführung in Machine Learning",
    course_name: "KI Grundlagen",
    planned_date: new Date().toISOString(),
    planned_time: "14:00",
    status: "completed",
    comprehension_score: 85,
    progress: 100,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "2",
    course_id: "course-1",
    topic_name: "Neuronale Netze und Deep Learning",
    course_name: "KI Grundlagen",
    planned_date: new Date(Date.now() + 86400000).toISOString(),
    planned_time: "10:00",
    status: "planned",
    comprehension_score: null,
    progress: 45,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "3",
    course_id: "course-2",
    topic_name: "Datenstrukturen und Algorithmen",
    course_name: "Programmierung",
    planned_date: new Date(Date.now() + 172800000).toISOString(),
    planned_time: "16:00",
    status: "planned",
    comprehension_score: null,
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "4",
    course_id: "course-2",
    topic_name: "Objektorientierte Programmierung",
    course_name: "Programmierung",
    planned_date: new Date(Date.now() - 86400000).toISOString(),
    planned_time: "14:00",
    status: "completed",
    comprehension_score: 92,
    progress: 100,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "5",
    course_id: "course-3",
    topic_name: "Datenbankdesign und SQL",
    course_name: "Datenbanken",
    planned_date: new Date(Date.now() - 172800000).toISOString(),
    planned_time: "09:00",
    status: "skipped",
    comprehension_score: null,
    progress: 30,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: "6",
    course_id: "course-3",
    topic_name: "NoSQL Datenbanken",
    course_name: "Datenbanken",
    planned_date: new Date(Date.now() + 259200000).toISOString(),
    planned_time: "11:00",
    status: "planned",
    comprehension_score: null,
    progress: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

const getStatusBadge = (status: LearningUnit["status"]) => {
  switch (status) {
    case "completed":
      return (
        <Badge
          variant="outline"
          className="flex gap-1 px-1.5 text-muted-foreground [&_svg]:size-3"
        >
          <CheckCircle2Icon className="text-green-500 dark:text-green-400" />
          Abgeschlossen
        </Badge>
      )
    case "planned":
      return (
        <Badge
          variant="outline"
          className="flex gap-1 px-1.5 text-muted-foreground [&_svg]:size-3"
        >
          <LoaderIcon className="animate-spin" />
          In Bearbeitung
        </Badge>
      )
    case "skipped":
      return (
        <Badge
          variant="outline"
          className="flex gap-1 px-1.5 text-muted-foreground [&_svg]:size-3"
        >
          Übersprungen
        </Badge>
      )
    case "rescheduled":
      return (
        <Badge
          variant="outline"
          className="flex gap-1 px-1.5 text-muted-foreground [&_svg]:size-3"
        >
          Verschoben
        </Badge>
      )
    default:
      return null
  }
}

export function LearningUnitsTable() {
  const [selectedRows, setSelectedRows] = React.useState<Set<string>>(new Set())

  const toggleRowSelection = (id: string) => {
    const newSelection = new Set(selectedRows)
    if (newSelection.has(id)) {
      newSelection.delete(id)
    } else {
      newSelection.add(id)
    }
    setSelectedRows(newSelection)
  }

  const toggleAllSelection = () => {
    if (selectedRows.size === dummyLearningUnits.length) {
      setSelectedRows(new Set())
    } else {
      setSelectedRows(new Set(dummyLearningUnits.map((unit) => unit.id)))
    }
  }

  return (
    <div className="flex w-full flex-col gap-6 px-4 lg:px-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Lerneinheiten</h2>
          <p className="text-sm text-muted-foreground">
            Übersicht über deine aktuellen Lerneinheiten
          </p>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-muted">
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={selectedRows.size === dummyLearningUnits.length}
                  onCheckedChange={toggleAllSelection}
                  aria-label="Select all"
                />
              </TableHead>
              <TableHead>Lerneinheit</TableHead>
              <TableHead>Kurs</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Fortschritt</TableHead>
              <TableHead className="text-right">Verständnis</TableHead>
              <TableHead>Geplant für</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {dummyLearningUnits.map((unit) => (
              <TableRow
                key={unit.id}
                data-state={selectedRows.has(unit.id) && "selected"}
              >
                <TableCell>
                  <Checkbox
                    checked={selectedRows.has(unit.id)}
                    onCheckedChange={() => toggleRowSelection(unit.id)}
                    aria-label={`Select ${unit.topic_name}`}
                  />
                </TableCell>
                <TableCell className="font-medium">
                  {unit.topic_name}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="px-1.5 text-muted-foreground">
                    {unit.course_name}
                  </Badge>
                </TableCell>
                <TableCell>{getStatusBadge(unit.status)}</TableCell>
                <TableCell className="text-right">
                  {unit.progress}%
                </TableCell>
                <TableCell className="text-right">
                  {unit.comprehension_score !== null
                    ? `${unit.comprehension_score}%`
                    : "N/A"}
                </TableCell>
                <TableCell>
                  {format(new Date(unit.planned_date), "dd.MM.yyyy")} {unit.planned_time}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        className="flex size-8 text-muted-foreground data-[state=open]:bg-muted"
                        size="icon"
                      >
                        <MoreVerticalIcon />
                        <span className="sr-only">Open menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-32">
                      <DropdownMenuItem>Bearbeiten</DropdownMenuItem>
                      <DropdownMenuItem>Details</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem>Löschen</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <div>
          {selectedRows.size} von {dummyLearningUnits.length} ausgewählt
        </div>
      </div>
    </div>
  )
}
