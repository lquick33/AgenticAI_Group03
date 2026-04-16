"use client"

import * as React from "react"
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react"
import { createClient } from "@/lib/supabase/client"
import { getFlashcardTaskStatus, cancelFlashcardTask, type FlashcardTaskStatus } from "@/lib/api/study"
import { calculateProcessingProgress, type ProcessingProgressData } from "@/lib/utils/progress"
import { toast } from "sonner"

export type TaskType = 'pdf_processing' | 'flashcard_generation'
export type TaskStatus =
  | 'pending'
  | 'uploading'
  | 'processing'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'error'

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
  totalPages?: number
  completedPages?: number
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

type TaskPollUpdate = Partial<BackgroundTask> & { _deleted?: true }

type CourseMaterialStatusRow = {
  processing_status: 'uploading' | 'processing' | 'completed' | 'error'
  page_count: number | null
  summary: string | null
  classification: string | null
}

const FINAL_TASK_STATUSES: readonly TaskStatus[] = ['completed', 'failed', 'cancelled', 'error']
const STORAGE_KEY = 'background_tasks'
const BackgroundTasksContext = createContext<BackgroundTasksContextValue | null>(null)

function isActiveTask(task: BackgroundTask): boolean {
  return !FINAL_TASK_STATUSES.includes(task.status)
}

function loadTasksFromStorage(): BackgroundTask[] {
  if (typeof window === 'undefined') return []

  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []

    const tasks = JSON.parse(stored) as Array<Omit<BackgroundTask, 'createdAt'> & { createdAt: string }>
    return tasks.map((task) => ({
      ...task,
      createdAt: new Date(task.createdAt),
    }))
  } catch {
    return []
  }
}

function saveTasksToStorage(tasks: BackgroundTask[]) {
  if (typeof window === 'undefined') return

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks.filter(isActiveTask)))
  } catch {
    // Ignore storage errors.
  }
}

function isDeletedUpdate(update: TaskPollUpdate): boolean {
  return update._deleted === true
}

interface BackgroundTasksProviderProps {
  children: React.ReactNode
}

export function BackgroundTasksProvider({ children }: BackgroundTasksProviderProps) {
  const [tasks, setTasks] = useState<BackgroundTask[]>(() => loadTasksFromStorage())
  const [userId, setUserId] = useState<string | null>(null)
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [supabase] = useState(() => createClient())

  useEffect(() => {
    const fetchUser = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser()

      if (user) {
        setUserId(user.id)
      }
    }

    void fetchUser()
  }, [supabase])

  useEffect(() => {
    saveTasksToStorage(tasks)
  }, [tasks])

  const activeTasks = tasks.filter(isActiveTask)
  const isPolling = activeTasks.length > 0

  const addTask = useCallback((task: Omit<BackgroundTask, 'createdAt'>) => {
    setTasks((prev) => {
      const exists = prev.some((existingTask) => existingTask.id === task.id)
      if (exists) {
        return prev.map((existingTask) =>
          existingTask.id === task.id ? { ...existingTask, ...task } : existingTask
        )
      }

      return [...prev, { ...task, createdAt: new Date() }]
    })
  }, [])

  const removeTask = useCallback((taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId))
  }, [])

  const updateTask = useCallback((taskId: string, updates: Partial<BackgroundTask>) => {
    setTasks((prev) =>
      prev.map((task) => (task.id === taskId ? { ...task, ...updates } : task))
    )
  }, [])

  const cancelTask = useCallback(
    async (taskId: string) => {
      const task = tasks.find((candidate) => candidate.id === taskId)
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
    },
    [tasks, updateTask, userId]
  )

  const getTasksByMaterial = useCallback(
    (materialId: string) => tasks.filter((task) => task.materialId === materialId),
    [tasks]
  )

  const getTasksByCourse = useCallback(
    (courseId: string) => tasks.filter((task) => task.courseId === courseId),
    [tasks]
  )

  const pollPdfProcessingStatus = useCallback(
    async (task: BackgroundTask): Promise<TaskPollUpdate | null> => {
      if (!task.materialId || task.materialId.startsWith('upload-') || task.status === 'uploading') {
        return null
      }

      try {
        const { data: materialData, error: materialError } = await supabase
          .from('course_materials')
          .select('processing_status, page_count, summary, classification')
          .eq('id', task.materialId)
          .single<CourseMaterialStatusRow>()

        if (materialError) {
          if (materialError.code === 'PGRST116') {
            return { _deleted: true }
          }

          return { status: 'error', stageMessage: 'Fehler beim Laden' }
        }

        if (!materialData) {
          return { _deleted: true }
        }

        const { count: completedPages } = await supabase
          .from('page_analyses')
          .select('*', { count: 'exact', head: true })
          .eq('course_material_id', task.materialId)

        const progressData: ProcessingProgressData = {
          status: materialData.processing_status,
          completedPages: completedPages ?? 0,
          totalPages: materialData.page_count ?? 0,
          hasSummary: Boolean(materialData.summary),
          hasClassification: Boolean(materialData.classification),
        }

        const progressResult = calculateProcessingProgress(progressData)

        return {
          status: materialData.processing_status,
          progress: progressResult.progress,
          stage: progressResult.stage,
          stageMessage: progressResult.stageMessage,
          totalPages: materialData.page_count ?? undefined,
          completedPages: completedPages ?? 0,
        }
      } catch (error) {
        console.error('Error polling PDF status:', error)
        return null
      }
    },
    [supabase]
  )

  const pollFlashcardStatus = useCallback(
    async (task: BackgroundTask): Promise<TaskPollUpdate | null> => {
      if (!task.taskId || !userId) return null

      try {
        const status = await getFlashcardTaskStatus(task.taskId, userId)
        const progress =
          status.total_pages > 0
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
          status: status.status,
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

        const errorMessage = error instanceof Error ? error.message : String(error)
        if (
          errorMessage.includes('404') ||
          errorMessage.includes('Task not found') ||
          errorMessage.includes('HTTP 404')
        ) {
          return {
            status: 'failed',
            progress: task.progress,
            stageMessage: 'Prozess nicht gefunden (Server Neustart?)',
            cardsGenerated: 0,
            totalPages: 0,
            completedPages: 0,
          }
        }

        return null
      }
    },
    [userId]
  )

  const pollAllTasks = useCallback(async () => {
    if (activeTasks.length === 0) {
      return
    }

    for (const task of activeTasks) {
      let updates: TaskPollUpdate | null = null

      if (task.type === 'pdf_processing') {
        updates = await pollPdfProcessingStatus(task)
      } else if (task.type === 'flashcard_generation') {
        updates = await pollFlashcardStatus(task)
      }

      if (!updates) {
        continue
      }

      if (isDeletedUpdate(updates)) {
        removeTask(task.id)
        continue
      }

      const previousStatus = task.status
      updateTask(task.id, updates)

      if (updates.status === previousStatus) {
        continue
      }

      if (updates.status === 'completed') {
        if (task.type === 'pdf_processing') {
          toast.success(`"${task.materialName}" wurde verarbeitet`)
        } else {
          toast.success(`Karteikarten für "${task.materialName}" erstellt`)
        }
      } else if (updates.status === 'failed' || updates.status === 'error') {
        toast.error(`Fehler bei "${task.materialName}"`, {
          description: updates.stageMessage,
        })
      }
    }
  }, [activeTasks, pollPdfProcessingStatus, pollFlashcardStatus, removeTask, updateTask])

  useEffect(() => {
    if (activeTasks.length === 0) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      return
    }
    const initialPollId = window.setTimeout(() => {
      void pollAllTasks()
    }, 0)

    if (!pollingIntervalRef.current) {
      pollingIntervalRef.current = setInterval(() => {
        void pollAllTasks()
      }, 3000)
    }

    return () => {
      clearTimeout(initialPollId)
    }
  }, [activeTasks.length, pollAllTasks])

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const completedTasks = tasks.filter((task) => FINAL_TASK_STATUSES.includes(task.status))
    if (completedTasks.length === 0) {
      return
    }

    const timeoutId = setTimeout(() => {
      setTasks((prev) =>
        prev.filter(
          (task) =>
            !FINAL_TASK_STATUSES.includes(task.status) ||
            new Date().getTime() - new Date(task.createdAt).getTime() < 30000
        )
      )
    }, 30000)

    return () => clearTimeout(timeoutId)
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

export function useBackgroundTasks() {
  const context = useContext(BackgroundTasksContext)
  if (!context) {
    throw new Error('useBackgroundTasks must be used within a BackgroundTasksProvider')
  }
  return context
}

export function useBackgroundTasksOptional() {
  return useContext(BackgroundTasksContext)
}


