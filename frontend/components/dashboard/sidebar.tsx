"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BookOpen,
  Bot,
  LayoutDashboard,
  Settings2,
  Sparkles,
} from "lucide-react"

import { NavMain, type NavMainItem } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { useSettings } from "@/components/settings/settings-context"
import { BackgroundTasksIndicator } from "@/components/background-tasks"

interface DashboardSidebarProps {
  user: {
    name: string
    email: string
    avatar: string
  }
  courses?: Array<{
    id: string
    title: string
  }>
}

export function DashboardSidebar({ user, courses = [], ...props }: DashboardSidebarProps & React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()
  const { openSettings } = useSettings()

  // Sample teams data - in a real app, this would come from your data source
  const teams = [
    {
      name: "Lernkompanien",
      logo: Sparkles,
      plan: "Student",
    },
  ]

  const navMain: NavMainItem[] = [
    {
      title: "Dashboard",
      url: "/dashboard",
      icon: LayoutDashboard,
      isActive: pathname === "/dashboard",
    },
    {
      title: "Kurse",
      url: "/dashboard/courses",
      icon: BookOpen,
      isActive: pathname?.startsWith("/dashboard/courses"),
    },
    {
      title: "Quick Chat",
      url: "/dashboard/chat",
      icon: Bot,
      isActive: pathname?.startsWith("/dashboard/chat"),
    },
    {
      title: "Einstellungen",
      url: "#",
      icon: Settings2,
      onClick: openSettings,
    },
  ]

  // Transform courses to projects format
  const projects = courses.map((course) => ({
    name: course.title,
    url: `/dashboard/courses/${course.id}`,
    icon: BookOpen,
  }))

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={teams} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
        <NavProjects projects={projects} />
      </SidebarContent>
      <SidebarFooter>
        <BackgroundTasksIndicator />
        <NavUser user={user} />
      </SidebarFooter>
    </Sidebar>
  )
}
