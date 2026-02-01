import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { CoursesTable } from '@/components/courses/courses-table'
import { CreateCourseDialog } from '@/components/courses/create-course-dialog'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { SettingsWrapper } from '@/components/settings'
import type { CourseWithStats } from '@/types'

export default async function CoursesPage() {
  const session = await requireAuth()
  const supabase = await createClient()

  // Get user
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

  // Fetch courses with statistics
  const { data: courses, error: coursesError } = await supabase
    .from('courses')
    .select(`
      *,
      course_materials (
        id,
        page_count,
        created_at,
        page_analyses (
          id
        )
      )
    `)
    .eq('user_id', user.id)
    .order('updated_at', { ascending: false })

  if (coursesError) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading courses: {coursesError.message}</p>
      </div>
    )
  }

  // Transform data to include statistics
  const coursesWithStats: CourseWithStats[] = (courses || []).map((course: any) => {
    const materials = course.course_materials || []
    
    // Count page_analyses from nested course_materials
    const analyzedPages = materials.reduce((sum: number, m: any) => {
      return sum + (m.page_analyses?.length || 0)
    }, 0)
    
    const materialCount = materials.length
    const totalPages = materials.reduce((sum: number, m: any) => sum + (m.page_count || 0), 0)
    
    const lastUpdated = materials.length > 0
      ? materials.reduce((latest: string | null, m: any) => {
          if (!latest) return m.created_at
          return new Date(m.created_at) > new Date(latest) ? m.created_at : latest
        }, null)
      : null

    return {
      ...course,
      material_count: materialCount,
      analyzed_pages: analyzedPages,
      total_pages: totalPages,
      last_updated: lastUpdated,
    }
  })

  // Prepare user data for sidebar
  const userData = {
    name: user.email?.split('@')[0] || 'User',
    email: user.email || '',
    avatar: '',
  }

  // Transform courses for sidebar (only id and title needed)
  const sidebarCourses = (courses || []).map((course) => ({
    id: course.id,
    title: course.title,
  }))

  return (
    <SettingsWrapper>
      <SidebarProvider>
        <DashboardSidebar variant="inset" user={userData} courses={sidebarCourses} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear z-20 relative">
            <div className="flex w-full items-center justify-between gap-1 px-4 lg:gap-2 lg:px-6">
              <div className="flex items-center gap-2">
                <SidebarTrigger className="-ml-1 relative z-30" />
                <Separator
                  orientation="vertical"
                  className="mx-2 data-[orientation=vertical]:h-4"
                />
                <h1 className="text-base font-medium">Kurse</h1>
              </div>
              <CreateCourseDialog userId={user.id} />
            </div>
          </header>
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
                <div className="px-4 lg:px-6">
                  <CoursesTable courses={coursesWithStats} />
                </div>
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
