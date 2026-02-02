import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { StudyReader } from '@/components/study/study-reader'
import { NoPageScroll } from '@/components/study/no-page-scroll'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { SettingsWrapper } from '@/components/settings'
import { notFound } from 'next/navigation'

interface StudyPageProps {
  params: Promise<{ id: string; materialId: string }>
  searchParams: Promise<{ page?: string }>
}

export default async function StudyPage({ params, searchParams }: StudyPageProps) {
  const { id: courseId, materialId } = await params
  const { page: pageParam } = await searchParams
  
  // Parse initial page from query param (for deep linking from Quick Chat)
  const initialPage = pageParam ? parseInt(pageParam, 10) : undefined
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

  // Fetch course material
  const { data: material, error: materialError } = await supabase
    .from('course_materials')
    .select('*')
    .eq('id', materialId)
    .eq('user_id', user.id)
    .eq('course_id', courseId)
    .single()

  if (materialError || !material) {
    notFound()
  }

  // Get signed URL for PDF from Supabase Storage
  const { data: signedUrlData, error: urlError } = await supabase.storage
    .from('course_materials')
    .createSignedUrl(material.file_path, 3600) // 1 hour expiry

  if (urlError || !signedUrlData) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading PDF file: {urlError?.message || 'Unknown error'}</p>
      </div>
    )
  }

  // Fetch courses for sidebar
  const { data: courses } = await supabase
    .from('courses')
    .select('id, title')
    .eq('user_id', user.id)
    .order('updated_at', { ascending: false })

  // Get current course name
  const currentCourse = courses?.find(c => c.id === courseId)

  // Prepare user data for sidebar
  const userData = {
    name: user.email?.split('@')[0] || 'User',
    email: user.email || '',
    avatar: '',
  }

  return (
    <SettingsWrapper>
      <NoPageScroll />
      <SidebarProvider className="h-svh">
        <DashboardSidebar variant="inset" user={userData} courses={courses || []} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear z-20 relative">
            <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
              <SidebarTrigger className="-ml-1 relative z-30" />
              <Separator
                orientation="vertical"
                className="mx-2 data-[orientation=vertical]:h-4"
              />
              <h1 className="text-base font-medium">{material.file_name}</h1>
            </div>
          </header>
          <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
            <div className="h-full max-h-full min-h-0 overflow-hidden">
              <StudyReader
                materialId={materialId}
                materialName={material.file_name}
                courseId={courseId}
                courseName={currentCourse?.title}
                pdfUrl={signedUrlData.signedUrl}
                pageCount={material.page_count}
                userId={user.id}
                initialPage={initialPage}
              />
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
