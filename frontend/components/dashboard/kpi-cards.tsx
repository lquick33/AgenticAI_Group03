"use client"

import * as React from "react"
import { Loader2, MinusIcon, TrendingDownIcon, TrendingUpIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { getStudyHistory, type StudyHistoryEntry } from "@/lib/api/study"
import { type StudyHistoryServerData } from "./progress-chart"

interface KPICardsProps {
  userId: string
  courseCount: number
  initialData?: StudyHistoryServerData[] | null
}

interface KPIData {
  cardsThisWeek: number
  cardsPreviousWeek: number
  timeThisWeekMinutes: number
  timePreviousWeekMinutes: number
  retentionThisWeek: number
  retentionPreviousWeek: number
  isDemo: boolean
}

const DEMO_KPI_DATA: KPIData = {
  cardsThisWeek: 156,
  cardsPreviousWeek: 142,
  timeThisWeekMinutes: 95,
  timePreviousWeekMinutes: 82,
  retentionThisWeek: 78,
  retentionPreviousWeek: 73,
  isDemo: true,
}

function calculateKPIs(data: StudyHistoryEntry[]): KPIData {
  const today = new Date()
  const oneWeekAgo = new Date(today)
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  const twoWeeksAgo = new Date(today)
  twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14)

  let cardsThisWeek = 0
  let cardsPreviousWeek = 0
  let timeThisWeekSeconds = 0
  let timePreviousWeekSeconds = 0
  let goodEasyThisWeek = 0
  let totalThisWeek = 0
  let goodEasyPreviousWeek = 0
  let totalPreviousWeek = 0

  for (const entry of data) {
    const entryDate = new Date(entry.date)

    if (entryDate >= oneWeekAgo) {
      cardsThisWeek += entry.cards_reviewed
      timeThisWeekSeconds += entry.time_spent_seconds
      goodEasyThisWeek += entry.good_count + entry.easy_count
      totalThisWeek += entry.cards_reviewed
    } else if (entryDate >= twoWeeksAgo) {
      cardsPreviousWeek += entry.cards_reviewed
      timePreviousWeekSeconds += entry.time_spent_seconds
      goodEasyPreviousWeek += entry.good_count + entry.easy_count
      totalPreviousWeek += entry.cards_reviewed
    }
  }

  const retentionThisWeek = totalThisWeek > 0 ? (goodEasyThisWeek / totalThisWeek) * 100 : 0
  const retentionPreviousWeek =
    totalPreviousWeek > 0 ? (goodEasyPreviousWeek / totalPreviousWeek) * 100 : 0

  return {
    cardsThisWeek,
    cardsPreviousWeek,
    timeThisWeekMinutes: Math.round(timeThisWeekSeconds / 60),
    timePreviousWeekMinutes: Math.round(timePreviousWeekSeconds / 60),
    retentionThisWeek,
    retentionPreviousWeek,
    isDemo: false,
  }
}

function calculateKPIsFromServerData(data: StudyHistoryServerData[]): KPIData {
  const today = new Date()
  const oneWeekAgo = new Date(today)
  oneWeekAgo.setDate(oneWeekAgo.getDate() - 7)
  const twoWeeksAgo = new Date(today)
  twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14)

  let cardsThisWeek = 0
  let cardsPreviousWeek = 0
  let timeThisWeekSeconds = 0
  let timePreviousWeekSeconds = 0
  let goodEasyThisWeek = 0
  let totalThisWeek = 0
  let goodEasyPreviousWeek = 0
  let totalPreviousWeek = 0

  for (const entry of data) {
    const entryDate = new Date(entry.study_date)

    if (entryDate >= oneWeekAgo) {
      cardsThisWeek += entry.cards_reviewed
      timeThisWeekSeconds += entry.time_spent_seconds
      goodEasyThisWeek += entry.good_count + entry.easy_count
      totalThisWeek += entry.cards_reviewed
    } else if (entryDate >= twoWeeksAgo) {
      cardsPreviousWeek += entry.cards_reviewed
      timePreviousWeekSeconds += entry.time_spent_seconds
      goodEasyPreviousWeek += entry.good_count + entry.easy_count
      totalPreviousWeek += entry.cards_reviewed
    }
  }

  const retentionThisWeek = totalThisWeek > 0 ? (goodEasyThisWeek / totalThisWeek) * 100 : 0
  const retentionPreviousWeek =
    totalPreviousWeek > 0 ? (goodEasyPreviousWeek / totalPreviousWeek) * 100 : 0

  return {
    cardsThisWeek,
    cardsPreviousWeek,
    timeThisWeekMinutes: Math.round(timeThisWeekSeconds / 60),
    timePreviousWeekMinutes: Math.round(timePreviousWeekSeconds / 60),
    retentionThisWeek,
    retentionPreviousWeek,
    isDemo: false,
  }
}

function formatTrend(
  current: number,
  previous: number,
  suffix = ""
): { text: string; direction: "up" | "down" | "neutral" } {
  const diff = current - previous
  if (diff > 0) {
    return { text: `+${diff}${suffix}`, direction: "up" }
  }
  if (diff < 0) {
    return { text: `${diff}${suffix}`, direction: "down" }
  }
  return { text: "0", direction: "neutral" }
}

function formatTime(minutes: number): string {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
  return `${minutes}m`
}

function TrendIcon({ direction }: { direction: "up" | "down" | "neutral" }) {
  if (direction === "up") return <TrendingUpIcon className="size-3" />
  if (direction === "down") return <TrendingDownIcon className="size-3" />
  return <MinusIcon className="size-3" />
}

function getTrendVariant(direction: "up" | "down" | "neutral") {
  if (direction === "up") {
    return "success" as const
  }
  if (direction === "down") {
    return "warning" as const
  }
  return "secondary" as const
}

export function KPICards({ userId, courseCount, initialData }: KPICardsProps) {
  const getInitialKpiData = (): KPIData | null => {
    if (initialData && initialData.length > 0) {
      const calculated = calculateKPIsFromServerData(initialData)
      if (calculated.cardsThisWeek === 0 && calculated.cardsPreviousWeek === 0) {
        return DEMO_KPI_DATA
      }
      return calculated
    }
    return null
  }

  const hasInitialData = Boolean(initialData && initialData.length > 0)
  const [kpiData, setKpiData] = React.useState<KPIData | null>(getInitialKpiData)
  const [isLoading, setIsLoading] = React.useState(!hasInitialData && !getInitialKpiData())

  React.useEffect(() => {
    if (!userId) {
      return
    }

    async function fetchData() {
      try {
        if (!hasInitialData) {
          const cachedResponse = await getStudyHistory(userId, 14, true)
          if (cachedResponse.status === "success" && cachedResponse.data.length > 0) {
            const calculated = calculateKPIs(cachedResponse.data)
            setKpiData(
              calculated.cardsThisWeek === 0 && calculated.cardsPreviousWeek === 0
                ? DEMO_KPI_DATA
                : calculated
            )
            setIsLoading(false)
          }
        }

        const freshResponse = await getStudyHistory(userId, 14, false)
        if (freshResponse.status === "success") {
          const calculated = calculateKPIs(freshResponse.data)
          setKpiData(
            calculated.cardsThisWeek === 0 && calculated.cardsPreviousWeek === 0
              ? DEMO_KPI_DATA
              : calculated
          )
        }
      } catch (err) {
        console.error("Error fetching KPI data:", err)
        setKpiData((current) => current ?? DEMO_KPI_DATA)
      } finally {
        setIsLoading(false)
      }
    }

    void fetchData()
  }, [userId, hasInitialData])

  const cardsTrend = kpiData ? formatTrend(kpiData.cardsThisWeek, kpiData.cardsPreviousWeek) : null
  const timeTrend = kpiData
    ? formatTrend(kpiData.timeThisWeekMinutes, kpiData.timePreviousWeekMinutes, "m")
    : null
  const retentionTrend = kpiData
    ? formatTrend(
        Math.round(kpiData.retentionThisWeek),
        Math.round(kpiData.retentionPreviousWeek),
        "%"
      )
    : null

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-4">
      <Card className="overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.18),_transparent_55%),var(--app-surface)]">
        <CardHeader className="gap-4">
          <div className="space-y-2">
            <CardDescription>Aktive Kurse</CardDescription>
            <CardTitle className="text-3xl font-semibold tabular-nums">{courseCount}</CardTitle>
          </div>
          <Badge variant="secondary" className="w-fit">
            Bibliothek aktiv
          </Badge>
        </CardHeader>
        <CardFooter className="items-start gap-1 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Eingeschriebene Kurse</p>
          <p>Alle Materialien und Lernpfade an einem Ort.</p>
        </CardFooter>
      </Card>

      <Card className="overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.14),_transparent_55%),var(--app-surface)]">
        <CardHeader className="gap-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <CardDescription>
                Karten diese Woche
                {kpiData?.isDemo ? <span className="ml-2 text-xs text-muted-foreground/70">(Demo)</span> : null}
              </CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">
                {isLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : kpiData?.cardsThisWeek ?? 0}
              </CardTitle>
            </div>
            {cardsTrend ? (
              <Badge variant={getTrendVariant(cardsTrend.direction)} className="gap-1.5">
                <TrendIcon direction={cardsTrend.direction} />
                {cardsTrend.text}
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardFooter className="items-start gap-1 text-sm text-muted-foreground">
          <p className="flex items-center gap-2 font-medium text-foreground">
            Wiederholungen in 7 Tagen
            {cardsTrend ? <TrendIcon direction={cardsTrend.direction} /> : null}
          </p>
          <p>Verglichen mit der Vorwoche.</p>
        </CardFooter>
      </Card>

      <Card className="overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.12),_transparent_55%),var(--app-surface)]">
        <CardHeader className="gap-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <CardDescription>Lernzeit diese Woche</CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">
                {isLoading ? (
                  <Loader2 className="h-6 w-6 animate-spin" />
                ) : (
                  formatTime(kpiData?.timeThisWeekMinutes ?? 0)
                )}
              </CardTitle>
            </div>
            {timeTrend ? (
              <Badge variant={getTrendVariant(timeTrend.direction)} className="gap-1.5">
                <TrendIcon direction={timeTrend.direction} />
                {timeTrend.text}
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardFooter className="items-start gap-1 text-sm text-muted-foreground">
          <p className="flex items-center gap-2 font-medium text-foreground">
            Aktive Lernzeit
            {timeTrend ? <TrendIcon direction={timeTrend.direction} /> : null}
          </p>
          <p>Fokuszeit statt reiner Anwesenheit.</p>
        </CardFooter>
      </Card>

      <Card className="overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_55%),var(--app-surface)]">
        <CardHeader className="gap-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <CardDescription>Erfolgsquote</CardDescription>
              <CardTitle className="text-3xl font-semibold tabular-nums">
                {isLoading ? (
                  <Loader2 className="h-6 w-6 animate-spin" />
                ) : (
                  `${Math.round(kpiData?.retentionThisWeek ?? 0)}%`
                )}
              </CardTitle>
            </div>
            {retentionTrend ? (
              <Badge variant={getTrendVariant(retentionTrend.direction)} className="gap-1.5">
                <TrendIcon direction={retentionTrend.direction} />
                {retentionTrend.text}
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardFooter className="items-start gap-1 text-sm text-muted-foreground">
          <p className="flex items-center gap-2 font-medium text-foreground">
            Gut- und Einfach-Antworten
            {retentionTrend ? <TrendIcon direction={retentionTrend.direction} /> : null}
          </p>
          <p>Ein schneller Blick auf die Qualitaet deiner Wiederholungen.</p>
        </CardFooter>
      </Card>
    </div>
  )
}
