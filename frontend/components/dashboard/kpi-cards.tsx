"use client"

import * as React from "react"
import { TrendingDownIcon, TrendingUpIcon, MinusIcon, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getStudyHistory, type StudyHistoryEntry } from "@/lib/api/study"

interface KPICardsProps {
  userId: string
  courseCount: number
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

// Demo data for new users
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
      // This week
      cardsThisWeek += entry.cards_reviewed
      timeThisWeekSeconds += entry.time_spent_seconds
      goodEasyThisWeek += entry.good_count + entry.easy_count
      totalThisWeek += entry.cards_reviewed
    } else if (entryDate >= twoWeeksAgo) {
      // Previous week
      cardsPreviousWeek += entry.cards_reviewed
      timePreviousWeekSeconds += entry.time_spent_seconds
      goodEasyPreviousWeek += entry.good_count + entry.easy_count
      totalPreviousWeek += entry.cards_reviewed
    }
  }

  const retentionThisWeek = totalThisWeek > 0 ? (goodEasyThisWeek / totalThisWeek) * 100 : 0
  const retentionPreviousWeek = totalPreviousWeek > 0 ? (goodEasyPreviousWeek / totalPreviousWeek) * 100 : 0

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

function formatTrend(current: number, previous: number, suffix: string = ""): { text: string; direction: "up" | "down" | "neutral" } {
  const diff = current - previous
  if (diff > 0) {
    return { text: `+${diff}${suffix}`, direction: "up" }
  } else if (diff < 0) {
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

export function KPICards({ userId, courseCount }: KPICardsProps) {
  const [kpiData, setKpiData] = React.useState<KPIData | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  React.useEffect(() => {
    if (!userId) return

    async function fetchData() {
      try {
        // Fetch cached data first for instant display
        const cachedResponse = await getStudyHistory(userId, 14, true)
        if (cachedResponse.status === "success" && cachedResponse.data.length > 0) {
          const calculated = calculateKPIs(cachedResponse.data)
          // Use demo data if no activity this week
          if (calculated.cardsThisWeek === 0 && calculated.cardsPreviousWeek === 0) {
            setKpiData(DEMO_KPI_DATA)
          } else {
            setKpiData(calculated)
          }
          setIsLoading(false)
        }

        // Then fetch fresh data
        const freshResponse = await getStudyHistory(userId, 14, false)
        if (freshResponse.status === "success") {
          const calculated = calculateKPIs(freshResponse.data)
          // Use demo data if no activity
          if (calculated.cardsThisWeek === 0 && calculated.cardsPreviousWeek === 0) {
            setKpiData(DEMO_KPI_DATA)
          } else {
            setKpiData(calculated)
          }
        }
      } catch (err) {
        console.error("Error fetching KPI data:", err)
        // On error, show demo data
        setKpiData(DEMO_KPI_DATA)
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [userId])

  const cardsTrend = kpiData ? formatTrend(kpiData.cardsThisWeek, kpiData.cardsPreviousWeek) : null
  const timeTrend = kpiData ? formatTrend(kpiData.timeThisWeekMinutes, kpiData.timePreviousWeekMinutes, "m") : null
  const retentionTrend = kpiData ? formatTrend(
    Math.round(kpiData.retentionThisWeek), 
    Math.round(kpiData.retentionPreviousWeek), 
    "%"
  ) : null

  return (
    <div className="*:data-[slot=card]:shadow-xs @xl/main:grid-cols-2 @5xl/main:grid-cols-4 grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card dark:*:data-[slot=card]:bg-card lg:px-6">
      {/* Active Courses */}
      <Card className="@container/card">
        <CardHeader className="relative">
          <CardDescription>Aktive Kurse</CardDescription>
          <CardTitle className="@[250px]/card:text-3xl text-2xl font-semibold tabular-nums">
            {courseCount}
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Eingeschriebene Kurse
          </div>
          <div className="text-muted-foreground">
            In deiner Bibliothek
          </div>
        </CardFooter>
      </Card>

      {/* Cards Reviewed This Week */}
      <Card className="@container/card">
        <CardHeader className="relative">
          <CardDescription>
            Karten diese Woche
            {kpiData?.isDemo && <span className="ml-2 text-xs text-muted-foreground/60">(Demo)</span>}
          </CardDescription>
          <CardTitle className="@[250px]/card:text-3xl text-2xl font-semibold tabular-nums">
            {isLoading ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              kpiData?.cardsThisWeek ?? 0
            )}
          </CardTitle>
          {cardsTrend && (
            <div className="absolute right-4 top-4">
              <Badge variant="outline" className="flex gap-1 rounded-lg text-xs">
                <TrendIcon direction={cardsTrend.direction} />
                {cardsTrend.text}
              </Badge>
            </div>
          )}
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Wiederholungen in 7 Tagen
            {cardsTrend && <TrendIcon direction={cardsTrend.direction} />}
          </div>
          <div className="text-muted-foreground">
            vs. Vorwoche
          </div>
        </CardFooter>
      </Card>

      {/* Study Time This Week */}
      <Card className="@container/card">
        <CardHeader className="relative">
          <CardDescription>Lernzeit diese Woche</CardDescription>
          <CardTitle className="@[250px]/card:text-3xl text-2xl font-semibold tabular-nums">
            {isLoading ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              formatTime(kpiData?.timeThisWeekMinutes ?? 0)
            )}
          </CardTitle>
          {timeTrend && (
            <div className="absolute right-4 top-4">
              <Badge variant="outline" className="flex gap-1 rounded-lg text-xs">
                <TrendIcon direction={timeTrend.direction} />
                {timeTrend.text}
              </Badge>
            </div>
          )}
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Aktive Lernzeit
            {timeTrend && <TrendIcon direction={timeTrend.direction} />}
          </div>
          <div className="text-muted-foreground">
            vs. Vorwoche
          </div>
        </CardFooter>
      </Card>

      {/* Retention Rate */}
      <Card className="@container/card">
        <CardHeader className="relative">
          <CardDescription>Erfolgsquote</CardDescription>
          <CardTitle className="@[250px]/card:text-3xl text-2xl font-semibold tabular-nums">
            {isLoading ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              `${Math.round(kpiData?.retentionThisWeek ?? 0)}%`
            )}
          </CardTitle>
          {retentionTrend && (
            <div className="absolute right-4 top-4">
              <Badge variant="outline" className="flex gap-1 rounded-lg text-xs">
                <TrendIcon direction={retentionTrend.direction} />
                {retentionTrend.text}
              </Badge>
            </div>
          )}
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Gut/Einfach Antworten
            {retentionTrend && <TrendIcon direction={retentionTrend.direction} />}
          </div>
          <div className="text-muted-foreground">
            vs. Vorwoche
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}
