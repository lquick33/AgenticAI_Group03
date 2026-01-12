import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { UploadSection } from '@/components/courses/upload-section'
import { CourseMaterialsList } from '@/components/courses/course-materials-list'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { notFound } from 'next/navigation'
import type { Course, CourseMaterial } from '@/types'

interface CourseDetailPageProps {
  params: Promise<{ id: string }>
}

export default async function CourseDetailPage({ params }: CourseDetailPageProps) {
  const { id } = await params
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

  // Fetch course details
  const { data: course, error: courseError } = await supabase
    .from('courses')
    .select('*')
    .eq('id', id)
    .eq('user_id', user.id)
    .single()

  if (courseError || !course) {
    notFound()
  }

  // Fetch course materials
  const { data: materials, error: materialsError } = await supabase
    .from('course_materials')
    .select('*')
    .eq('course_id', id)
    .order('created_at', { ascending: false })

  if (materialsError) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading materials: {materialsError.message}</p>
      </div>
    )
  }

  // Calculate statistics
  const materialCount = materials?.length || 0
  const totalPages = materials?.reduce((sum, m) => sum + (m.page_count || 0), 0) || 0
  
  // Fetch page analyses count
  const { count: analyzedPages } = await supabase
    .from('page_analyses')
    .select('*', { count: 'exact', head: true })
    .in(
      'course_material_id',
      materials?.map((m) => m.id) || []
    )

  const progress = totalPages > 0 ? Math.round(((analyzedPages || 0) / totalPages) * 100) : 0

  // Prepare user data for sidebar
  const userData = {
    name: user.email?.split('@')[0] || 'User',
    email: user.email || '',
    avatar: '',
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    const date = new Date(dateString)
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  return (
    <SidebarProvider>
      <DashboardSidebar variant="inset" user={userData} />
      <SidebarInset>
        <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear z-20 relative">
          <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
            <SidebarTrigger className="-ml-1 relative z-30" />
            <Separator
              orientation="vertical"
              className="mx-2 data-[orientation=vertical]:h-4"
            />
            <h1 className="text-base font-medium">{course.title}</h1>
          </div>
        </header>
        <div className="flex flex-1 flex-col">
          <div className="@container/main flex flex-1 flex-col gap-2">
            <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
              {/* Course Info Card */}
              <div className="px-4 lg:px-6">
                <Card>
                  <CardHeader>
                    <CardTitle>{course.title}</CardTitle>
                    <CardDescription>
                      {course.description || 'Keine Beschreibung'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Materialien</p>
                        <p className="text-2xl font-bold">{materialCount}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Gesamt Seiten</p>
                        <p className="text-2xl font-bold">{totalPages}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Progress</p>
                        <p className="text-2xl font-bold">{progress}%</p>
                      </div>
                    </div>
                    {course.exam_date && (
                      <div className="mt-4 pt-4 border-t">
                        <p className="text-sm text-muted-foreground">Prüfungsdatum</p>
                        <p className="text-lg font-semibold">{formatDate(course.exam_date)}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Upload Section */}
              <div className="px-4 lg:px-6">
                <UploadSection courseId={id} />
              </div>

              {/* Materials List */}
              <div className="px-4 lg:px-6">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold">Hochgeladene Materialien</h2>
                  <p className="text-sm text-muted-foreground">
                    Übersicht aller hochgeladenen Vorlesungsmaterialien
                  </p>
                </div>
                <CourseMaterialsList materials={(materials || []) as CourseMaterial[]} />
              </div>
            </div>
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
