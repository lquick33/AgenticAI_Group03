"use client"

import * as React from "react"
import {
  ArrowUpCircleIcon,
  BarChartIcon,
  MapIcon,
  GraduationCapIcon,
  BookOpenIcon,
  CheckSquareIcon,
  BotIcon,
  HelpCircleIcon,
  LayoutDashboardIcon,
  SearchIcon,
  SettingsIcon,
  UsersIcon,
} from "lucide-react"

import { NavDocuments } from "@/components/nav-documents"
import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const data = {
  user: {
    name: "Lernende/r",
    email: "student@lernkompanien.de",
    avatar: "/avatars/student.jpg",
  },
  navMain: [
    {
      title: "Übersicht",
      url: "#",
      icon: LayoutDashboardIcon,
    },
    {
      title: "Lernpfad",
      url: "#",
      icon: MapIcon,
    },
    {
      title: "Wissensstand",
      url: "#",
      icon: BarChartIcon,
    },
    {
      title: "Kurse",
      url: "#",
      icon: GraduationCapIcon,
    },
    {
      title: "Lerngruppen",
      url: "#",
      icon: UsersIcon,
    },
  ],
  navSecondary: [
    {
      title: "Einstellungen",
      url: "#",
      icon: SettingsIcon,
    },
    {
      title: "Hilfe",
      url: "#",
      icon: HelpCircleIcon,
    },
    {
      title: "Suchen",
      url: "#",
      icon: SearchIcon,
    },
  ],
  documents: [
    {
      name: "Meine Notizen",
      url: "#",
      icon: BookOpenIcon,
    },
    {
      name: "Prüfungen",
      url: "#",
      icon: CheckSquareIcon,
    },
    {
      name: "Lernassistent",
      url: "#",
      icon: BotIcon,
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:!p-1.5"
            >
              <a href="#">
                <ArrowUpCircleIcon className="h-5 w-5" />
                <span className="text-base font-semibold">Lernkompanien</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
        <NavDocuments items={data.documents} />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
    </Sidebar>
  )
}
