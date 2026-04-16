import { Layers3, LibraryBig } from "lucide-react"

import { CoursesTable } from "@/components/courses/courses-table"
import { CreateCourseDialog } from "@/components/courses/create-course-dialog"
import { DashboardSidebar } from "@/components/dashboard/sidebar"
import { SettingsWrapper } from "@/components/settings"
import { Separator } from "@/components/ui/separator"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { requireAuth } from "@/lib/auth"
import { createClient } from "@/lib/supabase/server"
import type { CourseWithStats } from "@/types"

interface CourseMaterialStatsRow {
  id: string
  page_count: number | null
  created_at: string
  page_analyses: Array<{ id: string }> | null
}

interface CourseRow
  extends Omit<CourseWithStats, "material_count" | "analyzed_pages" | "total_pages" | "last_updated"> {
  course_materials: CourseMaterialStatsRow[] | null
}

export default async function CoursesPage() {
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

  const { data: courses, error: coursesError } = await supabase
    .from("courses")
    .select(
      `
      *,
      course_materials (
        id,
        page_count,
        created_at,
        page_analyses (
          id
        )
      )
    `
    )
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })

  if (coursesError) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading courses: {coursesError.message}</p>
      </div>
    )
  }

  const courseRows = (courses ?? []) as CourseRow[]
  const coursesWithStats: CourseWithStats[] = courseRows.map((course) => {
    const materials = course.course_materials ?? []
    const analyzedPages = materials.reduce(
      (sum, material) => sum + (material.page_analyses?.length ?? 0),
      0
    )
    const materialCount = materials.length
    const totalPages = materials.reduce((sum, material) => sum + (material.page_count ?? 0), 0)
    const lastUpdated = materials.reduce<string | null>((latest, material) => {
      if (!latest) {
        return material.created_at
      }

      return new Date(material.created_at) > new Date(latest) ? material.created_at : latest
    }, null)

    return {
      ...course,
      material_count: materialCount,
      analyzed_pages: analyzedPages,
      total_pages: totalPages,
      last_updated: lastUpdated,
    }
  })

  const userData = {
    name: user.email?.split("@")[0] || "User",
    email: user.email || "",
    avatar: "",
  }

  const sidebarCourses = courseRows.map((course) => ({
    id: course.id,
    title: course.title,
  }))

  const totalMaterials = coursesWithStats.reduce((sum, course) => sum + course.material_count, 0)
  const totalPages = coursesWithStats.reduce((sum, course) => sum + course.total_pages, 0)

  return (
    <SettingsWrapper>
      <SidebarProvider>
        <DashboardSidebar variant="inset" user={userData} courses={sidebarCourses} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 relative z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-white/50 backdrop-blur-sm transition-[width,height] ease-linear dark:bg-transparent">
            <div className="flex w-full items-center justify-between gap-1 px-4 lg:gap-2 lg:px-6">
              <div className="flex items-center gap-2">
                <SidebarTrigger className="-ml-1 relative z-30" />
                <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
                <h1 className="text-base font-medium">Kurse</h1>
              </div>
              <CreateCourseDialog userId={user.id} />
            </div>
          </header>
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="app-shell">
                <section className="app-hero">
                  <div className="app-hero__header">
                    <div className="app-hero__content">
                      <span className="app-hero__eyebrow">
                        <LibraryBig className="h-3.5 w-3.5" />
                        Kursbibliothek
                      </span>
                      <h2 className="app-hero__title">Organisiere deine Vorlesungen, Materialien und Lernpfade in einer klaren Bibliothek.</h2>
                      <p className="app-hero__description">
                        Hier entsteht dein produktiver Einstiegspunkt fuer jedes Fach: von hochgeladenen PDFs ueber den Lernfortschritt bis zur spaeteren Flashcard-Erstellung.
                      </p>
                    </div>
                    <div className="app-hero__meta">
                      <div className="app-stat">
                        <span className="app-stat__label">Kurse</span>
                        <span className="app-stat__value">{coursesWithStats.length}</span>
                      </div>
                      <div className="app-stat">
                        <span className="app-stat__label">Materialien</span>
                        <span className="app-stat__value">{totalMaterials}</span>
                      </div>
                      <div className="app-stat">
                        <span className="app-stat__label">Seiten</span>
                        <span className="app-stat__value">{totalPages}</span>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="app-section">
                  <div className="app-section__header">
                    <div>
                      <h3 className="app-section__title">Kursuebersicht</h3>
                      <p className="app-section__description">
                        Vergleiche Materialien, Fortschritt und Aktualitaet deiner Kurse, bevor du in einen Kursraum wechselst.
                      </p>
                    </div>
                    <span className="app-subtle-chip">
                      <Layers3 className="h-4 w-4" />
                      {coursesWithStats.length} aktive Bereiche
                    </span>
                  </div>
                  <CoursesTable courses={coursesWithStats} />
                </section>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
