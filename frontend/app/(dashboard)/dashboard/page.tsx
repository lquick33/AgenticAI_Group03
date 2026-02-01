import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { KPICards } from '@/components/dashboard/kpi-cards'
import { ProgressChart } from '@/components/dashboard/progress-chart'
import { LearningUnitsTable } from '@/components/dashboard/learning-units-table'
import { AnkiSyncStatus } from '@/components/dashboard/anki-sync-status'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { SettingsWrapper } from '@/components/settings'

export default async function DashboardPage() {
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

  // Fetch courses for sidebar
  const { data: courses } = await supabase
    .from('courses')
    .select('id, title')
    .eq('user_id', user.id)
    .order('updated_at', { ascending: false })

  // Prepare user data for sidebar
  const userData = {
    name: user.email?.split('@')[0] || 'User',
    email: user.email || '',
    avatar: '',
  }

  return (
    <SettingsWrapper>
      <SidebarProvider>
        <DashboardSidebar variant="inset" user={userData} courses={courses || []} />
        <SidebarInset>
          <header className="group-has-data-[collapsible=icon]/sidebar-wrapper:h-12 flex h-12 shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear z-20 relative">
            <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
              <SidebarTrigger className="-ml-1 relative z-30" />
              <Separator
                orientation="vertical"
                className="mx-2 data-[orientation=vertical]:h-4"
              />
              <h1 className="text-base font-medium">Dashboard</h1>
            </div>
          </header>
          <div className="flex flex-1 flex-col">
            <div className="@container/main flex flex-1 flex-col gap-2">
              <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
                <div className="px-4 lg:px-6">
                  <AnkiSyncStatus />
                </div>
                <KPICards userId={user.id} courseCount={courses?.length ?? 0} />
                <div className="px-4 lg:px-6">
                  <ProgressChart userId={user.id} />
                </div>
                <LearningUnitsTable />
              </div>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
