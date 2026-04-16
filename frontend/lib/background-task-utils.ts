import type { BackgroundTask, TaskStatus } from "@/components/background-tasks"
import type { FlashcardTaskStatus } from "@/lib/api/study"

export const FINAL_BACKGROUND_TASK_STATUSES: readonly TaskStatus[] = [
  "completed",
  "failed",
  "cancelled",
  "error",
]

export function isFinalBackgroundTaskStatus(status: TaskStatus) {
  return FINAL_BACKGROUND_TASK_STATUSES.includes(status)
}

export function getPdfTaskForMaterial(
  tasks: BackgroundTask[] | undefined,
  materialId: string
) {
  return tasks?.find(
    (task) => task.type === "pdf_processing" && task.materialId === materialId
  )
}

export function getFlashcardTaskForMaterial(
  tasks: BackgroundTask[] | undefined,
  materialId: string
) {
  return tasks?.find(
    (task) => task.type === "flashcard_generation" && task.materialId === materialId
  )
}

export function toFlashcardTaskStatus(task: BackgroundTask): FlashcardTaskStatus {
  const mappedStatus: FlashcardTaskStatus["status"] =
    task.status === "running" ||
    task.status === "pending" ||
    task.status === "completed" ||
    task.status === "failed" ||
    task.status === "cancelled"
      ? task.status
      : "failed"

  return {
    task_id: task.taskId ?? task.id,
    status: mappedStatus,
    progress: Math.max(0, Math.min(1, task.progress / 100)),
    total_pages: task.totalPages ?? 0,
    processed_pages: task.completedPages ?? 0,
    cards_generated: task.cardsGenerated ?? 0,
    error_message:
      task.status === "failed" || task.status === "error"
        ? task.stageMessage
        : undefined,
    filename: undefined,
    anki_synced: task.ankiSynced,
    ankiweb_synced: task.ankiWebSynced,
    created_at: task.createdAt.getTime(),
    completed_at: isFinalBackgroundTaskStatus(task.status) ? Date.now() : undefined,
  }
}
