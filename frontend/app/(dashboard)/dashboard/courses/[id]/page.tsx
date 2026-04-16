import { BookOpen, CalendarDays, Layers3 } from "lucide-react"
import { notFound } from "next/navigation"

import { CourseMaterialsContainer } from "@/components/courses/course-materials-container"
import { CourseSettings } from "@/components/courses/course-settings"
import { ExamDateEditor } from "@/components/courses/exam-date-editor"
import { DashboardSidebar } from "@/components/dashboard/sidebar"
import { SettingsWrapper } from "@/components/settings"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { requireAuth } from "@/lib/auth"
import { createClient } from "@/lib/supabase/server"
import type { CourseMaterial } from "@/types"

interface CourseDetailPageProps {
  params: Promise<{ id: string }>
}

export default async function CourseDetailPage({ params }: CourseDetailPageProps) {
  const { id } = await params
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

  const { data: course, error: courseError } = await supabase
    .from("courses")
    .select("*")
    .eq("id", id)
    .eq("user_id", user.id)
    .single()

  if (courseError || !course) {
    notFound()
  }

  const { data: materials, error: materialsError } = await supabase
    .from("course_materials")
    .select("*")
    .eq("course_id", id)
    .order("created_at", { ascending: false })

  if (materialsError) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading materials: {materialsError.message}</p>
      </div>
    )
  }

  const materialCount = materials?.length || 0
  const totalPages = materials?.reduce((sum, material) => sum + (material.page_count || 0), 0) || 0

  const { count: analyzedPages } = await supabase
    .from("page_analyses")
    .select("*", { count: "exact", head: true })
    .in("course_material_id", materials?.map((material) => material.id) || [])

  const analyzedPageCount = analyzedPages || 0
  const progress = totalPages > 0 ? Math.round((analyzedPageCount / totalPages) * 100) : 0

  const { data: courses } = await supabase
    .from("courses")
    .select("id, title")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })

  const userData = {
    name: user.email?.split("@")[0] || "User",
    email: user.email || "",
    avatar: "",
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    const date = new Date(dateString)
    return date.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    })
  }

  const courseDescription = course.description?.trim() || "Noch keine Beschreibung hinterlegt."

  return (
    <SettingsWrapper>
      <SidebarProvider>
        <DashboardSidebar variant="inset" user={userData} courses={courses || []} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 relative z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-white/50 backdrop-blur-sm transition-[width,height] ease-linear dark:bg-transparent">
            <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
              <SidebarTrigger className="-ml-1 relative z-30" />
              <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
              <h1 className="text-base font-medium">{course.title}</h1>
            </div>
          </header>
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="app-shell">
                <section className="app-hero">
                  <div className="app-hero__header">
                    <div className="app-hero__content">
                      <span className="app-hero__eyebrow">
                        <BookOpen className="h-3.5 w-3.5" />
                        Kursraum
                      </span>
                      <h2 className="app-hero__title">{course.title}</h2>
                      <p className="app-hero__description">{courseDescription}</p>
                    </div>
                    <div className="flex flex-col items-start gap-3 sm:items-end">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={course.exam_date ? "info" : "secondary"}>
                          {course.exam_date ? `Pruefung: ${formatDate(course.exam_date)}` : "Kein Pruefungstermin"}
                        </Badge>
                        <CourseSettings
                          courseId={id}
                          userId={user.id}
                          initialDeduplicateFlashcards={course.deduplicate_flashcards ?? false}
                        />
                      </div>
                      <div className="app-hero__meta">
                        <div className="app-stat">
                          <span className="app-stat__label">Materialien</span>
                          <span className="app-stat__value">{materialCount}</span>
                        </div>
                        <div className="app-stat">
                          <span className="app-stat__label">Seiten</span>
                          <span className="app-stat__value">{totalPages}</span>
                        </div>
                        <div className="app-stat">
                          <span className="app-stat__label">Fortschritt</span>
                          <span className="app-stat__value">{progress}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="app-section">
                  <div className="app-section__header">
                    <div>
                      <h3 className="app-section__title">Kursstatus und Planung</h3>
                      <p className="app-section__description">
                        Alle wichtigen Rahmeninfos fuer diesen Kursraum, bevor du Materialien hochlaedst oder in den Study-Modus wechselst.
                      </p>
                    </div>
                  </div>
                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                    <div className="app-surface-panel gap-5">
                      <div className="grid gap-4 sm:grid-cols-3">
                        <div className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] p-4">
                          <p className="text-sm font-medium text-foreground">Analyse-Stand</p>
                          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{progress}%</p>
                          <p className="mt-2 text-sm text-muted-foreground">
                            {analyzedPageCount} von {totalPages} Seiten wurden bereits verarbeitet.
                          </p>
                        </div>
                        <div className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] p-4">
                          <p className="text-sm font-medium text-foreground">Kursbibliothek</p>
                          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{materialCount}</p>
                          <p className="mt-2 text-sm text-muted-foreground">PDFs stehen fuer Study Reader und Flashcards bereit.</p>
                        </div>
                        <div className="rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] p-4">
                          <p className="text-sm font-medium text-foreground">Arbeitsmodus</p>
                          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">Tutor</p>
                          <p className="mt-2 text-sm text-muted-foreground">Navigiere Seite fuer Seite durch den Stoff und baue daraus Kartenstapel auf.</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <span className="app-subtle-chip">
                          <Layers3 className="h-4 w-4" />
                          Kursraum fuer Upload, Analyse und Lernen
                        </span>
                        {course.exam_date ? (
                          <span className="app-subtle-chip">
                            <CalendarDays className="h-4 w-4" />
                            Termin am {formatDate(course.exam_date)}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="app-surface-panel app-surface-panel--muted gap-4">
                      <div className="space-y-2">
                        <h4 className="text-lg font-semibold tracking-tight text-foreground">Pruefungsdatum pflegen</h4>
                        <p className="text-sm text-muted-foreground">
                          Halte den Zieltermin aktuell, damit die Lernplanung den Kurs besser einordnen kann.
                        </p>
                      </div>
                      <ExamDateEditor courseId={id} userId={user.id} initialDate={course.exam_date} />
                    </div>
                  </div>
                </section>

                <CourseMaterialsContainer
                  courseId={id}
                  userId={user.id}
                  courseName={course.title}
                  initialMaterials={(materials || []) as CourseMaterial[]}
                  deduplicateFlashcards={course.deduplicate_flashcards ?? false}
                />
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
