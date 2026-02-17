import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { SettingsWrapper } from '@/components/settings'
import { QuickChatContent } from './quick-chat'
import { Search } from 'lucide-react'

export default async function QuickChatPage() {
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
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4" />
                <h1 className="text-base font-medium">Quick Chat</h1>
              </div>
            </div>
          </header>
          <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
            <QuickChatContent userId={user.id} />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SettingsWrapper>
  )
}
