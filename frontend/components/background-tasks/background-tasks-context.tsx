"use client"

import * as React from "react"
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react"
import { createClient } from "@/lib/supabase/client"
import { getFlashcardTaskStatus, cancelFlashcardTask, type FlashcardTaskStatus } from "@/lib/api/study"
import { calculateProcessingProgress, type ProcessingProgressData } from "@/lib/utils/progress"
import { toast } from "sonner"

// ============================================================================
// Types
// ============================================================================

export type TaskType = 'pdf_processing' | 'flashcard_generation'
export type TaskStatus = 'pending' | 'uploading' | 'processing' | 'running' | 'completed' | 'failed' | 'cancelled' | 'error'

export interface BackgroundTask {
  id: string
  type: TaskType
  materialId: string
  materialName: string
  courseId: string
  courseName?: string
  progress: number
  status: TaskStatus
  stage?: string
  stageMessage?: string
  createdAt: Date
  // PDF-specific fields
  totalPages?: number
  completedPages?: number
  // Flashcard-specific fields
  taskId?: string
  cardsGenerated?: number
  ankiSynced?: boolean
  ankiWebSynced?: boolean
}

interface BackgroundTasksContextValue {
  tasks: BackgroundTask[]
  activeTasks: BackgroundTask[]
  addTask: (task: Omit<BackgroundTask, 'createdAt'>) => void
  removeTask: (taskId: string) => void
  updateTask: (taskId: string, updates: Partial<BackgroundTask>) => void
  cancelTask: (taskId: string) => Promise<void>
  getTasksByMaterial: (materialId: string) => BackgroundTask[]
  getTasksByCourse: (courseId: string) => BackgroundTask[]
  isPolling: boolean
  userId: string | null
}

const BackgroundTasksContext = createContext<BackgroundTasksContextValue | null>(null)

// ============================================================================
// localStorage helpers
// ============================================================================

const STORAGE_KEY = 'background_tasks'

function loadTasksFromStorage(): BackgroundTask[] {
  if (typeof window === 'undefined') return []
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    const tasks = JSON.parse(stored) as BackgroundTask[]
    // Convert date strings back to Date objects
    return tasks.map(task => ({
      ...task,
      createdAt: new Date(task.createdAt)
    }))
  } catch {
    return []
  }
}

function saveTasksToStorage(tasks: BackgroundTask[]) {
  if (typeof window === 'undefined') return
  try {
    // Only save active tasks (not completed/failed/cancelled)
    const activeTasks = tasks.filter(t => 
      !['completed', 'failed', 'cancelled', 'error'].includes(t.status)
    )
    localStorage.setItem(STORAGE_KEY, JSON.stringify(activeTasks))
  } catch {
    // Ignore storage errors
  }
}

// ============================================================================
// Provider Component
// ============================================================================

interface BackgroundTasksProviderProps {
  children: React.ReactNode
}

export function BackgroundTasksProvider({ children }: BackgroundTasksProviderProps) {
  const [tasks, setTasks] = useState<BackgroundTask[]>([])
  const [isPolling, setIsPolling] = useState(false)
  const [userId, setUserId] = useState<string | null>(null)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const supabase = createClient()

  // Fetch user ID on mount
  useEffect(() => {
    const fetchUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        setUserId(user.id)
      }
    }
    fetchUser()
  }, [supabase.auth])

  // Load tasks from localStorage on mount
  useEffect(() => {
    const storedTasks = loadTasksFromStorage()
    if (storedTasks.length > 0) {
      setTasks(storedTasks)
    }
  }, [])

  // Save tasks to localStorage whenever they change
  useEffect(() => {
    saveTasksToStorage(tasks)
  }, [tasks])

  // Get active tasks (not completed/failed/cancelled)
  const activeTasks = tasks.filter(t => 
    !['completed', 'failed', 'cancelled', 'error'].includes(t.status)
  )

  // Add a new task
  const addTask = useCallback((task: Omit<BackgroundTask, 'createdAt'>) => {
    setTasks(prev => {
      // Check if task already exists
      const exists = prev.some(t => t.id === task.id)
      if (exists) {
        // Update existing task
        return prev.map(t => t.id === task.id ? { ...t, ...task } : t)
      }
      // Add new task
      return [...prev, { ...task, createdAt: new Date() }]
    })
  }, [])

  // Remove a task
  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId))
  }, [])

  // Update a task
  const updateTask = useCallback((taskId: string, updates: Partial<BackgroundTask>) => {
    setTasks(prev => prev.map(t => 
      t.id === taskId ? { ...t, ...updates } : t
    ))
  }, [])

  // Cancel a flashcard generation task
  const cancelTask = useCallback(async (taskId: string) => {
    const task = tasks.find(t => t.id === taskId)
    if (!task || task.type !== 'flashcard_generation' || !task.taskId || !userId) {
      return
    }

    try {
      await cancelFlashcardTask(task.taskId, userId)
      updateTask(taskId, { status: 'cancelled', stageMessage: 'Abgebrochen' })
      toast.info('Karteikarten-Generierung abgebrochen')
    } catch (error) {
      console.error('Failed to cancel task:', error)
      toast.error('Fehler beim Abbrechen')
    }
  }, [tasks, updateTask, userId])

  // Get tasks by material ID
  const getTasksByMaterial = useCallback((materialId: string) => {
    return tasks.filter(t => t.materialId === materialId)
  }, [tasks])

  // Get tasks by course ID
  const getTasksByCourse = useCallback((courseId: string) => {
    return tasks.filter(t => t.courseId === courseId)
  }, [tasks])

  // Poll for PDF processing status
  const pollPdfProcessingStatus = useCallback(async (task: BackgroundTask) => {
    // Skip if no materialId or if it's a temporary upload ID
    if (!task.materialId || task.materialId.startsWith('upload-')) return null
    // Skip if task is still in uploading state (not yet in database)
    if (task.status === 'uploading') return null

    try {
      // Query course_materials for status
      const { data: materialData, error: materialError } = await supabase
        .from('course_materials')
        .select('processing_status, page_count, summary, classification')
        .eq('id', task.materialId)
        .single()

      if (materialError) {
        // PGRST116 = "The result contains 0 rows" - material was deleted
        if (materialError.code === 'PGRST116') {
          return { _deleted: true } as any
        }
        return { status: 'error' as TaskStatus, stageMessage: 'Fehler beim Laden' }
      }
      
      if (!materialData) {
        return { _deleted: true } as any
      }

      // Get completed pages count
      const { count: completedPages } = await supabase
        .from('page_analyses')
        .select('*', { count: 'exact', head: true })
        .eq('course_material_id', task.materialId)

      // Calculate progress
      const progressData: ProcessingProgressData = {
        status: materialData.processing_status as 'uploading' | 'processing' | 'completed' | 'error',
        completedPages: completedPages || 0,
        totalPages: materialData.page_count || 0,
        hasSummary: !!materialData.summary,
        hasClassification: !!materialData.classification,
      }

      const progressResult = calculateProcessingProgress(progressData)

      return {
        status: materialData.processing_status as TaskStatus,
        progress: progressResult.progress,
        stage: progressResult.stage,
        stageMessage: progressResult.stageMessage,
        totalPages: materialData.page_count,
        completedPages: completedPages || 0,
      }
    } catch (error) {
      console.error('Error polling PDF status:', error)
      return null
    }
  }, [supabase])

  // Poll for flashcard generation status
  const pollFlashcardStatus = useCallback(async (task: BackgroundTask) => {
    if (!task.taskId || !userId) return null

    try {
      const status = await getFlashcardTaskStatus(task.taskId, userId)
      
      const progress = status.total_pages > 0 
        ? Math.round((status.processed_pages / status.total_pages) * 100)
        : 0

      let stageMessage = 'Wird generiert...'
      if (status.status === 'pending') {
        stageMessage = 'Warte auf Start...'
      } else if (status.status === 'running') {
        stageMessage = `Seite ${status.processed_pages} von ${status.total_pages}`
      } else if (status.status === 'completed') {
        stageMessage = `${status.cards_generated} Karten erstellt`
      } else if (status.status === 'failed') {
        stageMessage = status.error_message || 'Fehler aufgetreten'
      } else if (status.status === 'cancelled') {
        stageMessage = 'Abgebrochen'
      }

      return {
        status: status.status as TaskStatus,
        progress,
        stageMessage,
        cardsGenerated: status.cards_generated,
        totalPages: status.total_pages,
        completedPages: status.processed_pages,
        ankiSynced: status.anki_synced,
        ankiWebSynced: status.ankiweb_synced,
      }
    } catch (error) {
      console.error('Error polling flashcard status:', error)
      
      // Handle 404 (Task not found) - likely due to backend restart
      const errorMessage = error instanceof Error ? error.message : String(error)
      if (errorMessage.includes('404') || errorMessage.includes('Task not found') || errorMessage.includes('HTTP 404')) {
        return {
          status: 'failed' as TaskStatus,
          progress: task.progress,
          stageMessage: 'Prozess nicht gefunden (Server Neustart?)',
          cardsGenerated: 0,
          totalPages: 0,
          completedPages: 0,
        }
      }
      
      return null
    }
  }, [userId])

  // Main polling function
  const pollAllTasks = useCallback(async () => {
    const activeTasksList = tasks.filter(t => 
      !['completed', 'failed', 'cancelled', 'error'].includes(t.status)
    )

    if (activeTasksList.length === 0) {
      return
    }

    for (const task of activeTasksList) {
      let updates: Partial<BackgroundTask> | null = null

      if (task.type === 'pdf_processing') {
        updates = await pollPdfProcessingStatus(task)
      } else if (task.type === 'flashcard_generation') {
        updates = await pollFlashcardStatus(task)
      }

      if (updates) {
        // Check if the material was deleted
        if ((updates as any)._deleted) {
          removeTask(task.id)
          continue
        }
        
        const prevStatus = task.status
        updateTask(task.id, updates)

        // Show toast notifications for status changes
        if (updates.status !== prevStatus) {
          if (updates.status === 'completed') {
            if (task.type === 'pdf_processing') {
              toast.success(`"${task.materialName}" wurde verarbeitet`)
            } else {
              toast.success(`Karteikarten für "${task.materialName}" erstellt`)
            }
          } else if (updates.status === 'failed' || updates.status === 'error') {
            toast.error(`Fehler bei "${task.materialName}"`, {
              description: updates.stageMessage
            })
          }
        }
      }
    }
  }, [tasks, updateTask, removeTask, pollPdfProcessingStatus, pollFlashcardStatus])

  // Start/stop polling based on active tasks
  useEffect(() => {
    const hasActiveTasks = activeTasks.length > 0

    if (hasActiveTasks && !pollingIntervalRef.current) {
      setIsPolling(true)
      // Poll immediately on start
      pollAllTasks()
      // Then poll every 3 seconds
      pollingIntervalRef.current = setInterval(pollAllTasks, 3000)
    } else if (!hasActiveTasks && pollingIntervalRef.current) {
      setIsPolling(false)
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [activeTasks.length, pollAllTasks])

  // Cleanup completed tasks after a delay
  useEffect(() => {
    const completedTasks = tasks.filter(t => 
      ['completed', 'failed', 'cancelled', 'error'].includes(t.status)
    )

    if (completedTasks.length > 0) {
      // Remove completed tasks after 30 seconds
      const timeoutId = setTimeout(() => {
        setTasks(prev => prev.filter(t => 
          !['completed', 'failed', 'cancelled', 'error'].includes(t.status) ||
          // Keep tasks that completed less than 30 seconds ago
          (new Date().getTime() - new Date(t.createdAt).getTime()) < 30000
        ))
      }, 30000)

      return () => clearTimeout(timeoutId)
    }
  }, [tasks])

  const value: BackgroundTasksContextValue = {
    tasks,
    activeTasks,
    addTask,
    removeTask,
    updateTask,
    cancelTask,
    getTasksByMaterial,
    getTasksByCourse,
    isPolling,
    userId,
  }

  return (
    <BackgroundTasksContext.Provider value={value}>
      {children}
    </BackgroundTasksContext.Provider>
  )
}

// ============================================================================
// Hook
// ============================================================================

export function useBackgroundTasks() {
  const context = useContext(BackgroundTasksContext)
  if (!context) {
    throw new Error('useBackgroundTasks must be used within a BackgroundTasksProvider')
  }
  return context
}

// Optional hook that returns null if not in context (for optional usage)
export function useBackgroundTasksOptional() {
  return useContext(BackgroundTasksContext)
}
