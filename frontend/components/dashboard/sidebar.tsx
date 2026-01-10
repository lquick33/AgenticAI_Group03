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

import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavUser } from "@/components/nav-user"
import { TeamSwitcher } from "@/components/team-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"

interface DashboardSidebarProps {
  user: {
    name: string
    email: string
    avatar: string
  }
}

export function DashboardSidebar({ user, ...props }: DashboardSidebarProps & React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()

  // Sample teams data - in a real app, this would come from your data source
  const teams = [
    {
      name: "Lernkompanien",
      logo: Sparkles,
      plan: "Student",
    },
  ]

  const navMain = [
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
      items: [
        {
          title: "Alle Kurse",
          url: "/dashboard/courses",
        },
        {
          title: "Neuer Kurs",
          url: "/dashboard/courses/new",
        },
      ],
    },
    {
      title: "Quick Chat",
      url: "/dashboard/chat",
      icon: Bot,
      isActive: pathname?.startsWith("/dashboard/chat"),
    },
    {
      title: "Einstellungen",
      url: "/dashboard/settings",
      icon: Settings2,
      isActive: pathname?.startsWith("/dashboard/settings"),
      items: [
        {
          title: "Allgemein",
          url: "/dashboard/settings",
        },
        {
          title: "Profil",
          url: "/dashboard/settings/profile",
        },
        {
          title: "Benachrichtigungen",
          url: "/dashboard/settings/notifications",
        },
      ],
    },
  ]

  // Sample projects (courses) - in a real app, fetch from Supabase
  const projects = [
    {
      name: "KI Grundlagen",
      url: "/dashboard/courses/ki-grundlagen",
      icon: BookOpen,
    },
    {
      name: "Programmierung",
      url: "/dashboard/courses/programmierung",
      icon: BookOpen,
    },
    {
      name: "Datenbanken",
      url: "/dashboard/courses/datenbanken",
      icon: BookOpen,
    },
  ]

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
        <NavUser user={user} />
      </SidebarFooter>
    </Sidebar>
  )
}
