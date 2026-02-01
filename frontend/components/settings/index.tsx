"use client"

import { SettingsProvider } from "./settings-context"
import { SettingsDialog } from "./settings-dialog"

export { SettingsProvider, useSettings } from "./settings-context"
export { SettingsDialog } from "./settings-dialog"

/**
 * SettingsWrapper combines the SettingsProvider and SettingsDialog
 * for easy integration into dashboard pages.
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
    <SettingsProvider>
      {children}
      <SettingsDialog />
    </SettingsProvider>
  )
}
