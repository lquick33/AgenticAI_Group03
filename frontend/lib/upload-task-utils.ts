import type { BackgroundTask } from "@/components/background-tasks"
import type { FileUploadItem } from "@/components/courses/multi-file-upload-list"
import { getPdfTaskForMaterial } from "@/lib/background-task-utils"

export function mergeFilesWithPdfTasks(
  files: FileUploadItem[],
  tasks: BackgroundTask[] | undefined
): FileUploadItem[] {
  return files.map((file) => {
    if (!file.materialId) {
      return file
    }

    const task = getPdfTaskForMaterial(tasks, file.materialId)
    if (!task) {
      return file
    }

    const mappedStatus: FileUploadItem["status"] =
      task.status === "completed"
        ? "completed"
        : task.status === "failed" || task.status === "error"
          ? "error"
          : task.status === "uploading"
            ? "uploading"
            : "processing"

    return {
      ...file,
      status: mappedStatus,
      progress: task.progress,
      processingProgress: mappedStatus === "processing" || mappedStatus === "completed"
        ? task.progress
        : undefined,
      processingStage: task.stage,
      processingStageMessage: task.stageMessage,
      errorMessage:
        mappedStatus === "error" ? task.stageMessage ?? file.errorMessage : file.errorMessage,
    }
  })
}
