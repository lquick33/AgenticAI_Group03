"use client"

import { cn } from "@/lib/utils"
import { Loader } from "@/components/ui/loader"
import { Check, X } from "lucide-react"

export type TaskStatus = "pending" | "running" | "completed" | "error"

interface TaskProps {
  status: TaskStatus
  title: string
  description?: string
  children?: React.ReactNode
}

export function Task({ status, title, description, children }: TaskProps) {
  const getStatusStyles = () => {
    switch (status) {
      case "pending":
        return "border-gray-200 bg-gray-50"
      case "running":
        return "border-blue-200 bg-blue-50"
      case "completed":
        return "border-green-200 bg-green-50"
      case "error":
        return "border-red-200 bg-red-50"
      default:
        return "border-gray-200 bg-gray-50"
    }
  }

  const getIcon = () => {
    switch (status) {
      case "pending":
        return (
          <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
        )
      case "running":
        return <Loader size={16} className="text-blue-600" />
      case "completed":
        return <Check className="h-4 w-4 text-green-600" />
      case "error":
        return <X className="h-4 w-4 text-red-600" />
      default:
        return null
    }
  }

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 rounded-lg border transition-colors",
        getStatusStyles()
      )}
    >
      <div className="flex-shrink-0 mt-0.5">{getIcon()}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-medium text-gray-900 truncate">{title}</h4>
          {status === "running" && (
            <span className="text-xs text-blue-600 font-medium">läuft...</span>
          )}
        </div>
        {description && (
          <p className="text-xs text-gray-600 mt-1">{description}</p>
        )}
        {children && <div className="mt-2">{children}</div>}
      </div>
    </div>
  )
}

interface TaskListProps {
  children: React.ReactNode
  className?: string
}

export function TaskList({ children, className }: TaskListProps) {
  return <div className={cn("space-y-2", className)}>{children}</div>
}
