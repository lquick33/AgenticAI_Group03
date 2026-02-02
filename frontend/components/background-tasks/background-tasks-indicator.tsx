"use client"

import * as React from "react"
import { useState } from "react"
import { Loader2, Activity, CheckCircle2, XCircle, FileText, Sparkles, X, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { useBackgroundTasksOptional, type BackgroundTask } from "./background-tasks-context"

interface BackgroundTasksIndicatorProps {
  className?: string
}

function TaskIcon({ task }: { task: BackgroundTask }) {
  if (task.type === 'pdf_processing') {
    return <FileText className="h-4 w-4 text-blue-500" />
  }
  return <Sparkles className="h-4 w-4 text-amber-500" />
}

function TaskStatusIcon({ task }: { task: BackgroundTask }) {
  if (task.status === 'completed') {
    return <CheckCircle2 className="h-4 w-4 text-green-500" />
  }
  if (task.status === 'failed' || task.status === 'error') {
    return <XCircle className="h-4 w-4 text-red-500" />
  }
  if (task.status === 'cancelled') {
    return <XCircle className="h-4 w-4 text-muted-foreground" />
  }
  // Running/pending/processing
  return <Loader2 className="h-4 w-4 animate-spin text-primary" />
}

interface TaskItemProps {
  task: BackgroundTask
  onCancel?: () => void
  onDismiss?: () => void
}

function TaskItem({ task, onCancel, onDismiss }: TaskItemProps) {
  const isActive = !['completed', 'failed', 'cancelled', 'error'].includes(task.status)
  const canCancel = task.type === 'flashcard_generation' && isActive
  // Allow dismiss for: completed/failed/cancelled tasks, OR stuck uploading tasks (can be safely removed)
  const isStuckUploading = task.status === 'uploading'
  const canDismiss = !isActive || isStuckUploading

  return (
    <div className="flex flex-col gap-2 p-3 rounded-lg border border-gray-200 bg-gray-50">
      <div className="flex items-start gap-2">
        <TaskIcon task={task} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate text-gray-900">{task.materialName}</p>
          {task.courseName && (
            <p className="text-xs text-gray-500 truncate">{task.courseName}</p>
          )}
        </div>
        <TaskStatusIcon task={task} />
      </div>
      
      {isActive && (
        <div className="space-y-1">
          <Progress value={task.progress} className="h-1.5" />
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-gray-500 truncate flex-1">
              {task.stageMessage || 'Wird verarbeitet...'}
            </p>
            <span className="text-xs font-medium text-gray-600">
              {task.progress}%
            </span>
          </div>
        </div>
      )}
      
      {!isActive && task.stageMessage && (
        <p className="text-xs text-gray-500">{task.stageMessage}</p>
      )}

      {(canCancel || canDismiss) && (
        <div className="flex gap-2">
          {canCancel && onCancel && (
            <Button 
              variant="outline" 
              size="sm" 
              className="h-7 text-xs flex-1"
              onClick={onCancel}
            >
              Abbrechen
            </Button>
          )}
          {canDismiss && onDismiss && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-7 text-xs flex-1 text-gray-500 hover:text-gray-700"
              onClick={onDismiss}
            >
              <X className="h-3 w-3 mr-1" />
              {isStuckUploading ? 'Abbrechen' : 'Entfernen'}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

export function BackgroundTasksIndicator({ className }: BackgroundTasksIndicatorProps) {
  const [open, setOpen] = useState(false)
  const context = useBackgroundTasksOptional()

  // If no context, don't render anything
  if (!context) {
    return null
  }

  const { tasks, activeTasks, cancelTask, removeTask } = context
  const activeCount = activeTasks.length

  // Show recently completed tasks too (last 60 seconds for better visibility)
  const recentTasks = tasks.filter(t => {
    if (!['completed', 'failed', 'cancelled', 'error'].includes(t.status)) {
      return true
    }
    // Show completed tasks for 60 seconds
    const age = new Date().getTime() - new Date(t.createdAt).getTime()
    return age < 60000
  })

  // Don't render if no tasks at all
  if (recentTasks.length === 0) {
    return null
  }

  const handleCancel = async (taskId: string) => {
    await cancelTask(taskId)
  }

  const handleDismiss = (taskId: string) => {
    removeTask(taskId)
  }

  const handleClearAll = () => {
    // Remove all non-active tasks
    tasks.forEach(t => {
      if (['completed', 'failed', 'cancelled', 'error'].includes(t.status)) {
        removeTask(t.id)
      }
    })
  }

  const completedTasks = recentTasks.filter(t => 
    ['completed', 'failed', 'cancelled', 'error'].includes(t.status)
  )

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className={className}
            >
              {activeCount > 0 ? (
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              ) : (
                <Activity className="h-5 w-5 text-green-500" />
              )}
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">
                  {activeCount > 0 
                    ? `${activeCount} Prozess${activeCount > 1 ? 'e' : ''} aktiv`
                    : 'Prozesse abgeschlossen'
                  }
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {activeCount > 0 
                    ? 'Klicken für Details'
                    : `${recentTasks.length} kürzlich`
                  }
                </span>
              </div>
              {activeCount > 0 && (
                <Badge 
                  variant="secondary" 
                  className="h-5 min-w-5 px-1.5 text-xs font-medium ml-auto"
                >
                  {activeCount}
                </Badge>
              )}
            </SidebarMenuButton>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md bg-white">
            <DialogHeader>
              <DialogTitle className="flex items-center justify-between text-gray-900">
                <span>Hintergrundprozesse</span>
                <div className="flex items-center gap-2">
                  {activeCount > 0 && (
                    <Badge variant="outline" className="text-xs font-normal">
                      {activeCount} aktiv
                    </Badge>
                  )}
                  {completedTasks.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs text-gray-500 hover:text-gray-700"
                      onClick={handleClearAll}
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      Alle löschen
                    </Button>
                  )}
                </div>
              </DialogTitle>
            </DialogHeader>
            
            {recentTasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-gray-500">
                <Activity className="h-8 w-8 mb-2 opacity-50" />
                <p className="text-sm">Keine aktiven Prozesse</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                {recentTasks.map(task => (
                  <TaskItem 
                    key={task.id} 
                    task={task}
                    onCancel={task.type === 'flashcard_generation' ? () => handleCancel(task.id) : undefined}
                    onDismiss={() => handleDismiss(task.id)}
                  />
                ))}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
