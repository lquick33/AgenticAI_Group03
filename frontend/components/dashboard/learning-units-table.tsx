"use client"

import * as React from "react"
import { format } from "date-fns"
import { CheckCircle2Icon, LoaderIcon, MoreVerticalIcon } from "lucide-react"

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

const dummyLearningUnits: Array<LearningUnit & { course_name: string; progress: number }> = [
  {
    id: "1",
    course_id: "course-1",
    user_id: "user-1",
    title: "Einfuehrung in Machine Learning",
    course_name: "KI Grundlagen",
    start_time: "2026-01-15T10:00:00.000Z",
    end_time: "2026-01-15T12:00:00.000Z",
    status: "completed",
    comprehension_score: 85,
    progress: 100,
    created_at: "2026-01-15T10:00:00.000Z",
    updated_at: "2026-01-15T12:00:00.000Z",
  },
  {
    id: "2",
    course_id: "course-1",
    user_id: "user-1",
    title: "Neuronale Netze und Deep Learning",
    course_name: "KI Grundlagen",
    start_time: "2026-02-02T14:00:00.000Z",
    end_time: "2026-02-02T16:00:00.000Z",
    status: "planned",
    comprehension_score: null,
    progress: 45,
    created_at: "2026-01-20T09:00:00.000Z",
    updated_at: "2026-01-20T09:00:00.000Z",
  },
  {
    id: "3",
    course_id: "course-2",
    user_id: "user-1",
    title: "Datenstrukturen und Algorithmen",
    course_name: "Programmierung",
    start_time: "2026-02-03T10:00:00.000Z",
    end_time: "2026-02-03T12:00:00.000Z",
    status: "planned",
    comprehension_score: null,
    progress: 0,
    created_at: "2026-01-18T11:00:00.000Z",
    updated_at: "2026-01-18T11:00:00.000Z",
  },
  {
    id: "4",
    course_id: "course-2",
    user_id: "user-1",
    title: "Objektorientierte Programmierung",
    course_name: "Programmierung",
    start_time: "2026-01-30T09:00:00.000Z",
    end_time: "2026-01-30T11:00:00.000Z",
    status: "completed",
    comprehension_score: 92,
    progress: 100,
    created_at: "2026-01-25T08:00:00.000Z",
    updated_at: "2026-01-30T11:00:00.000Z",
  },
  {
    id: "5",
    course_id: "course-3",
    user_id: "user-1",
    title: "Datenbankdesign und SQL",
    course_name: "Datenbanken",
    start_time: "2026-01-28T15:00:00.000Z",
    end_time: "2026-01-28T17:00:00.000Z",
    status: "skipped",
    comprehension_score: null,
    progress: 30,
    created_at: "2026-01-22T10:00:00.000Z",
    updated_at: "2026-01-28T17:00:00.000Z",
  },
  {
    id: "6",
    course_id: "course-3",
    user_id: "user-1",
    title: "NoSQL Datenbanken",
    course_name: "Datenbanken",
    start_time: "2026-02-05T13:00:00.000Z",
    end_time: "2026-02-05T15:00:00.000Z",
    status: "planned",
    comprehension_score: null,
    progress: 0,
    created_at: "2026-01-22T10:00:00.000Z",
    updated_at: "2026-01-22T10:00:00.000Z",
  },
]

const getStatusBadge = (status: LearningUnit["status"]) => {
  switch (status) {
    case "completed":
      return (
        <Badge variant="success" className="gap-1.5">
          <CheckCircle2Icon className="h-3 w-3" />
          Abgeschlossen
        </Badge>
      )
    case "planned":
      return (
        <Badge variant="info" className="gap-1.5">
          <LoaderIcon className="h-3 w-3" />
          Geplant
        </Badge>
      )
    case "skipped":
      return <Badge variant="warning">Uebersprungen</Badge>
    case "rescheduled":
      return <Badge variant="secondary">Verschoben</Badge>
    default:
      return null
  }
}

export function LearningUnitsTable() {
  const [selectedRows, setSelectedRows] = React.useState<Set<string>>(new Set())

  const toggleRowSelection = (id: string) => {
    const nextSelection = new Set(selectedRows)
    if (nextSelection.has(id)) {
      nextSelection.delete(id)
    } else {
      nextSelection.add(id)
    }
    setSelectedRows(nextSelection)
  }

  const toggleAllSelection = () => {
    if (selectedRows.size === dummyLearningUnits.length) {
      setSelectedRows(new Set())
      return
    }
    setSelectedRows(new Set(dummyLearningUnits.map((unit) => unit.id)))
  }

  return (
    <section className="app-surface-panel gap-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h4 className="app-section__title">Lerneinheiten</h4>
          <p className="app-section__description">
            Eine ruhige Uebersicht ueber aktuelle Sessions, Prioritaeten und abgeschlossene Slots.
          </p>
        </div>
        <span className="app-subtle-chip">{dummyLearningUnits.length} Einheiten geplant</span>
      </div>

      <div className="app-table-shell">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={selectedRows.size === dummyLearningUnits.length}
                  onCheckedChange={toggleAllSelection}
                  aria-label="Alle Lerneinheiten auswaehlen"
                />
              </TableHead>
              <TableHead>Lerneinheit</TableHead>
              <TableHead>Kurs</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Fortschritt</TableHead>
              <TableHead className="text-right">Verstaendnis</TableHead>
              <TableHead>Geplant fuer</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {dummyLearningUnits.map((unit) => (
              <TableRow key={unit.id} data-state={selectedRows.has(unit.id) ? "selected" : undefined}>
                <TableCell>
                  <Checkbox
                    checked={selectedRows.has(unit.id)}
                    onCheckedChange={() => toggleRowSelection(unit.id)}
                    aria-label={`${unit.title} auswaehlen`}
                  />
                </TableCell>
                <TableCell className="min-w-[220px] align-top">
                  <div className="space-y-1">
                    <p className="font-medium text-foreground">{unit.title}</p>
                    <p className="text-xs text-muted-foreground">{format(new Date(unit.end_time), "HH:mm")} Ende</p>
                  </div>
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant="secondary">{unit.course_name}</Badge>
                </TableCell>
                <TableCell className="align-top">{getStatusBadge(unit.status)}</TableCell>
                <TableCell className="align-top text-right font-medium text-foreground">
                  {unit.progress}%
                </TableCell>
                <TableCell className="align-top text-right text-sm text-muted-foreground">
                  {unit.comprehension_score !== null ? `${unit.comprehension_score}%` : "-"}
                </TableCell>
                <TableCell className="align-top text-sm text-muted-foreground">
                  {format(new Date(unit.start_time), "dd.MM.yyyy HH:mm")}
                </TableCell>
                <TableCell className="align-top">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon-touch" aria-label={`Aktionen fuer ${unit.title}`}>
                        <MoreVerticalIcon className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-36">
                      <DropdownMenuItem>Bearbeiten</DropdownMenuItem>
                      <DropdownMenuItem>Details</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem>Loeschen</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {selectedRows.size} von {dummyLearningUnits.length} ausgewaehlt
        </span>
        <span>Demo-Daten fuer die Planungsansicht</span>
      </div>
    </section>
  )
}
