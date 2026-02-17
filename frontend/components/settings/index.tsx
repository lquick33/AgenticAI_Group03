"use client"

import { SettingsProvider } from "./settings-context"
import { SettingsDialog } from "./settings-dialog"
import { BackgroundTasksProvider } from "@/components/background-tasks"

export { SettingsProvider, useSettings } from "./settings-context"
export { SettingsDialog } from "./settings-dialog"

/**
 * SettingsWrapper combines the SettingsProvider, BackgroundTasksProvider,
 * and SettingsDialog for easy integration into dashboard pages.
 * 
 * Usage:
 * <SettingsWrapper>
 *   <SidebarProvider>
 *     <DashboardSidebar />
 *     ...
 *   </SidebarProvider>
 * </SettingsWrapper>
 */
export function SettingsWrapper({ children }: { children: React.ReactNode }) {
  return (
    <BackgroundTasksProvider>
      <SettingsProvider>
        {children}
        <SettingsDialog />
      </SettingsProvider>
    </BackgroundTasksProvider>
  )
}
