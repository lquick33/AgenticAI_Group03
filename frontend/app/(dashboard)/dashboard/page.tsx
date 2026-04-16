import Link from "next/link"
import { ArrowRight, Sparkles } from "lucide-react"

import { DashboardSidebar } from "@/components/dashboard/sidebar"
import { KPICards } from "@/components/dashboard/kpi-cards"
import { LearningUnitsTable } from "@/components/dashboard/learning-units-table"
import { ProgressChartLazy } from "@/components/dashboard/progress-chart-lazy"
import { SettingsWrapper } from "@/components/settings"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { requireAuth } from "@/lib/auth"
import { createClient } from "@/lib/supabase/server"

export default async function DashboardPage() {
  await requireAuth()
  const supabase = await createClient()

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  if (userError || !user) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading user data</p>
      </div>
    )
  }

  const { data: courses } = await supabase
    .from("courses")
    .select("id, title")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })

  const cutoffDate = new Date()
  cutoffDate.setDate(cutoffDate.getDate() - 90)
  const cutoffDateStr = cutoffDate.toISOString().split("T")[0]

  const { data: studyHistory } = await supabase
    .from("anki_study_history")
    .select(
      "study_date, cards_reviewed, time_spent_seconds, again_count, hard_count, good_count, easy_count, new_cards, review_cards, relearn_cards"
    )
    .eq("user_id", user.id)
    .gte("study_date", cutoffDateStr)
    .order("study_date", { ascending: true })

  const userData = {
    name: user.email?.split("@")[0] || "User",
    email: user.email || "",
    avatar: "",
  }

  const activeCourses = courses?.length ?? 0
  const trackedDays = studyHistory?.length ?? 0

  return (
    <SettingsWrapper>
      <SidebarProvider>
        <DashboardSidebar variant="inset" user={userData} courses={courses || []} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 relative z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-white/50 backdrop-blur-sm transition-[width,height] ease-linear dark:bg-transparent">
            <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
              <SidebarTrigger className="-ml-1 relative z-30" />
              <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
              <h1 className="text-base font-medium">Dashboard</h1>
            </div>
          </header>
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="app-shell">
                <section className="app-hero">
                  <div className="app-hero__header">
                    <div className="app-hero__content">
                      <span className="app-hero__eyebrow">
                        <Sparkles className="h-3.5 w-3.5" />
                        Lernzentrale
                      </span>
                      <h2 className="app-hero__title">
                        Behalte Kurse, Lernzeit und Wiederholungen in einem ruhigen Arbeitsraum im Blick.
                      </h2>
                      <p className="app-hero__description">
                        Dein Dashboard fasst Aktivitaet, Fortschritt und naechste Lernschritte zusammen, ohne dich mit zu vielen Einzelelementen zu ueberladen.
                      </p>
                    </div>
                    <div className="flex flex-col items-start gap-3 sm:items-end">
                      <Button asChild variant="accent">
                        <Link href="/dashboard/courses">
                          Kurse verwalten
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                      <div className="app-hero__meta">
                        <div className="app-stat">
                          <span className="app-stat__label">Aktive Kurse</span>
                          <span className="app-stat__value">{activeCourses}</span>
                        </div>
                        <div className="app-stat">
                          <span className="app-stat__label">Verlaufstage</span>
                          <span className="app-stat__value">{trackedDays}</span>
                        </div>
                        <div className="app-stat">
                          <span className="app-stat__label">Anki Sync</span>
                          <span className="app-stat__value">Bereit</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="app-section">
                  <div className="app-section__header">
                    <div>
                      <h3 className="app-section__title">Wochenueberblick</h3>
                      <p className="app-section__description">
                        Die wichtigsten Kennzahlen fuer Karten, Lernzeit und Erfolgsquote auf einen Blick.
                      </p>
                    </div>
                  </div>
                  <KPICards
                    userId={user.id}
                    courseCount={activeCourses}
                    initialData={studyHistory}
                  />
                </section>

                <section className="app-section">
                  <div className="app-section__header">
                    <div>
                      <h3 className="app-section__title">Analyse und Planung</h3>
                      <p className="app-section__description">
                        Kombiniere Langzeit-Trends mit den aktuell geplanten Lerneinheiten, um gezielter zu priorisieren.
                      </p>
                    </div>
                  </div>
                  <ProgressChartLazy userId={user.id} initialData={studyHistory} />
                  <LearningUnitsTable />
                </section>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
