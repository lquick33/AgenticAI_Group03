"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { format } from "date-fns"
import { Loader2 } from "lucide-react"

import { useIsMobile } from "@/hooks/use-mobile"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group"
import { getStudyHistory, type StudyHistoryEntry } from "@/lib/api/study"

interface ChartDataPoint {
  date: string
  cardsStudied: number
  timeSpentMinutes: number
}

// Type for data coming from server-side Supabase query
export interface StudyHistoryServerData {
  study_date: string
  cards_reviewed: number
  time_spent_seconds: number
  again_count: number
  hard_count: number
  good_count: number
  easy_count: number
  new_cards: number
  review_cards: number
  relearn_cards: number
}

// Transform server data to chart data points
function transformServerData(data: StudyHistoryServerData[]): ChartDataPoint[] {
  return data.map((entry) => ({
    date: entry.study_date,
    cardsStudied: entry.cards_reviewed,
    timeSpentMinutes: Math.round(entry.time_spent_seconds / 60),
  }))
}

// Generate demo data for new users
function generateDemoData(): ChartDataPoint[] {
  const data: ChartDataPoint[] = []
  const today = new Date()
  
  for (let i = 89; i >= 0; i--) {
    const date = new Date(today)
    date.setDate(date.getDate() - i)
    
    // Generate realistic-looking study pattern
    // Lower on weekends, variable on weekdays
    const dayOfWeek = date.getDay()
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6
    const baseCards = isWeekend ? 30 : 60
    const variance = Math.floor(Math.random() * 40)
    const cardsStudied = baseCards + variance
    
    data.push({
      date: date.toISOString().split('T')[0],
      cardsStudied,
      timeSpentMinutes: Math.round(cardsStudied * 0.5), // ~30 sec per card
    })
  }
  
  return data
}

const chartConfig = {
  cardsStudied: {
    label: "Karten gelernt",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig

interface ProgressChartProps {
  userId: string
  initialData?: StudyHistoryServerData[] | null
}

export function ProgressChart({ userId, initialData }: ProgressChartProps) {
  const isMobile = useIsMobile()
  const [timeRange, setTimeRange] = React.useState("30d")
  
  // Initialize with server-provided data for instant rendering
  const hasInitialData = initialData && initialData.length > 0
  const [chartData, setChartData] = React.useState<ChartDataPoint[]>(() => 
    hasInitialData ? transformServerData(initialData) : []
  )
  const [isLoading, setIsLoading] = React.useState(!hasInitialData)
  const [error, setError] = React.useState<string | null>(null)
  const [dataSource, setDataSource] = React.useState<"anki" | "cache" | "demo" | null>(
    hasInitialData ? "cache" : null
  )

  React.useEffect(() => {
    if (isMobile) {
      setTimeRange("7d")
    }
  }, [isMobile])

  // Fetch fresh study history data (skip cache fetch if we have server-provided initial data)
  React.useEffect(() => {
    if (!userId) return
    
    let isMounted = true
    // Track if we have real data (either from initial props or fetched)
    let hasRealData = hasInitialData
    
    async function fetchData() {
      // Step 1: Only fetch cached data if we don't have initial data from server
      if (!hasInitialData) {
        try {
          const cachedResponse = await getStudyHistory(userId, 90, true)
          
          if (isMounted && cachedResponse.status === "success" && cachedResponse.data.length > 0) {
            hasRealData = true
            setDataSource(cachedResponse.source)
            const transformed: ChartDataPoint[] = cachedResponse.data.map((entry: StudyHistoryEntry) => ({
              date: entry.date,
              cardsStudied: entry.cards_reviewed,
              timeSpentMinutes: Math.round(entry.time_spent_seconds / 60),
            }))
            setChartData(transformed)
            setIsLoading(false)
          }
        } catch (err) {
          console.error("Error fetching cached study history:", err)
        }
      }
      
      // Step 2: Fetch fresh data from Anki in the background
      try {
        const freshResponse = await getStudyHistory(userId, 90, false)
        
        if (isMounted && freshResponse.status === "success") {
          if (freshResponse.data.length > 0) {
            hasRealData = true
            setDataSource(freshResponse.source)
            const transformed: ChartDataPoint[] = freshResponse.data.map((entry: StudyHistoryEntry) => ({
              date: entry.date,
              cardsStudied: entry.cards_reviewed,
              timeSpentMinutes: Math.round(entry.time_spent_seconds / 60),
            }))
            setChartData(transformed)
          }
          setError(null)
        }
      } catch (err) {
        console.error("Error fetching fresh study history:", err)
      } finally {
        if (isMounted) {
          // If no real data, show demo data
          if (!hasRealData) {
            setChartData(generateDemoData())
            setDataSource("demo")
          }
          setIsLoading(false)
        }
      }
    }
    
    fetchData()
    
    return () => {
      isMounted = false
    }
  }, [userId, hasInitialData])

  // Filter data based on selected time range
  const filteredData = React.useMemo(() => {
    if (!chartData.length) return []
    
    const referenceDate = new Date()
    let daysToSubtract = 90
    if (timeRange === "30d") {
      daysToSubtract = 30
    } else if (timeRange === "7d") {
      daysToSubtract = 7
    }
    
    const startDate = new Date(referenceDate)
    startDate.setDate(startDate.getDate() - daysToSubtract)
    
    return chartData.filter((item) => {
      const date = new Date(item.date)
      return date >= startDate
    })
  }, [chartData, timeRange])

  // Calculate summary stats for the selected period
  const summaryStats = React.useMemo(() => {
    if (!filteredData.length) return { totalCards: 0, avgPerDay: 0 }
    
    const totalCards = filteredData.reduce((sum, d) => sum + d.cardsStudied, 0)
    const avgPerDay = Math.round(totalCards / filteredData.length)
    
    return { totalCards, avgPerDay }
  }, [filteredData])

  return (
    <Card className="@container/card">
      <CardHeader className="relative">
        <CardTitle>Lernfortschritt</CardTitle>
        <CardDescription>
          {isLoading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Lade Daten...
            </span>
          ) : error ? (
            <span className="text-destructive">{error}</span>
          ) : (
            <>
              <span className="@[540px]/card:block hidden">
                {summaryStats.totalCards} Karten in den letzten {timeRange === "90d" ? "3 Monaten" : timeRange === "30d" ? "30 Tagen" : "7 Tagen"}
                {dataSource === "cache" && " (gecached)"}
                {dataSource === "demo" && <span className="ml-1 text-muted-foreground/60">(Demo)</span>}
              </span>
              <span className="@[540px]/card:hidden">
                {summaryStats.totalCards} Karten
                {dataSource === "demo" && <span className="ml-1 text-muted-foreground/60">(Demo)</span>}
              </span>
            </>
          )}
        </CardDescription>
        <div className="absolute right-4 top-4">
          <ToggleGroup
            type="single"
            value={timeRange}
            onValueChange={(value) => value && setTimeRange(value)}
            variant="outline"
            className="@[767px]/card:flex hidden"
          >
            <ToggleGroupItem value="90d" className="h-8 px-2.5">
              Letzte 3 Monate
            </ToggleGroupItem>
            <ToggleGroupItem value="30d" className="h-8 px-2.5">
              Letzte 30 Tage
            </ToggleGroupItem>
            <ToggleGroupItem value="7d" className="h-8 px-2.5">
              Letzte 7 Tage
            </ToggleGroupItem>
          </ToggleGroup>
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger
              className="@[767px]/card:hidden flex w-40"
              aria-label="Zeitraum auswählen"
            >
              <SelectValue placeholder="Letzte 3 Monate" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="90d" className="rounded-lg">
                Letzte 3 Monate
              </SelectItem>
              <SelectItem value="30d" className="rounded-lg">
                Letzte 30 Tage
              </SelectItem>
              <SelectItem value="7d" className="rounded-lg">
                Letzte 7 Tage
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        {isLoading ? (
          <div className="flex h-[250px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex h-[250px] items-center justify-center text-muted-foreground">
            Keine Daten verfügbar
          </div>
        ) : filteredData.length === 0 ? (
          <div className="flex h-[250px] items-center justify-center text-muted-foreground">
            Noch keine Lernaktivitäten aufgezeichnet
          </div>
        ) : (
          <ChartContainer
            config={chartConfig}
            className="aspect-auto h-[250px] w-full"
          >
            <AreaChart data={filteredData}>
              <defs>
                <linearGradient id="fillCardsStudied" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="5%"
                    stopColor="var(--color-cardsStudied)"
                    stopOpacity={1.0}
                  />
                  <stop
                    offset="95%"
                    stopColor="var(--color-cardsStudied)"
                    stopOpacity={0.1}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={32}
                tickFormatter={(value) => {
                  const date = new Date(value)
                  return format(date, "d. MMM")
                }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                width={40}
                tickFormatter={(value) => `${value}`}
              />
              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    labelFormatter={(value) => {
                      return format(new Date(value), "d. MMMM yyyy")
                    }}
                    formatter={(value, name) => {
                      if (name === "cardsStudied") {
                        return [`${value} Karten`, "Gelernt"]
                      }
                      return [value, name]
                    }}
                    indicator="dot"
                  />
                }
              />
              <Area
                dataKey="cardsStudied"
                type="monotone"
                fill="url(#fillCardsStudied)"
                stroke="var(--color-cardsStudied)"
                strokeWidth={2}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}
