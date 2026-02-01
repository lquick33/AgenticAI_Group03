"use client"

import dynamic from 'next/dynamic'
import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import type { StudyHistoryServerData } from './progress-chart'

// OPTIMIZED: Lazy load the ProgressChart component to defer loading recharts library
const ProgressChart = dynamic(
  () => import('./progress-chart').then((mod) => mod.ProgressChart),
  {
    loading: () => (
      <Card>
        <CardHeader className="flex items-center gap-2 space-y-0 border-b py-5 sm:flex-row">
          <div className="grid flex-1 gap-1 text-center sm:text-left">
            <CardTitle>Lernfortschritt</CardTitle>
            <CardDescription>Deine Anki-Lernstatistiken</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[250px]">
          <div className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-muted-foreground">Chart wird geladen...</span>
          </div>
        </CardContent>
      </Card>
    ),
    ssr: false
  }
)

interface ProgressChartLazyProps {
  userId: string
  initialData?: StudyHistoryServerData[] | null
}

export function ProgressChartLazy({ userId, initialData }: ProgressChartLazyProps) {
  return <ProgressChart userId={userId} initialData={initialData} />
}
