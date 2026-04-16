"use client"

import { useCallback, useEffect, useMemo, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { useBackgroundTasksOptional } from "@/components/background-tasks"
import { CourseMaterialsList } from "@/components/courses/course-materials-list"
import { UploadSection } from "@/components/courses/upload-section"
import { isFinalBackgroundTaskStatus } from "@/lib/background-task-utils"
import { createClient } from "@/lib/supabase/client"
import type { CourseMaterial } from "@/types"

interface CourseMaterialsContainerProps {
  courseId: string
  userId: string
  courseName?: string
  initialMaterials: CourseMaterial[]
  deduplicateFlashcards?: boolean
}

export function CourseMaterialsContainer({
  courseId,
  userId,
  courseName,
  initialMaterials,
  deduplicateFlashcards = false,
}: CourseMaterialsContainerProps) {
  const queryClient = useQueryClient()

  const { data: materialsData, refetch, isFetching: isRefreshing } = useQuery({
    queryKey: ["courseMaterials", courseId],
    queryFn: async () => {
      const supabase = createClient()
      const { data, error } = await supabase
        .from("course_materials")
        .select("*")
        .eq("course_id", courseId)
        .order("created_at", { ascending: false })
      
      if (error) throw error
      return data as CourseMaterial[]
    },
    initialData: initialMaterials,
  })

  const materials = materialsData ?? initialMaterials
  const backgroundTasks = useBackgroundTasksOptional()
  const previousTaskStatusesRef = useRef<Map<string, string>>(new Map())

  const refreshMaterials = useCallback(async () => {
    await refetch()
  }, [refetch])

  const handleUploadSuccess = useCallback(() => {
    window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ["courseMaterials", courseId] })
    }, 300)
  }, [queryClient, courseId])

  useEffect(() => {
    if (!backgroundTasks) {
      return
    }

    materials.forEach((material) => {
      const isProcessing =
        material.processing_status === "processing" || material.processing_status === "uploading"
      if (!isProcessing) {
        return
      }

      const hasTask = backgroundTasks
        .getTasksByMaterial(material.id)
        .some((task) => task.type === "pdf_processing")

      if (!hasTask) {
        backgroundTasks.addTask({
          id: material.id,
          type: "pdf_processing",
          materialId: material.id,
          materialName: material.file_name.replace(/\.pdf$/i, ""),
          courseId,
          courseName,
          progress: material.processing_status === "uploading" ? 0 : 5,
          status: material.processing_status,
          stage: material.processing_status,
          stageMessage:
            material.processing_status === "uploading"
              ? "Wird hochgeladen..."
              : "Wird verarbeitet...",
        })
      }
    })
  }, [backgroundTasks, materials, courseId, courseName])

  const materialProgress = useMemo(() => {
    const progressByMaterial: Record<string, { progress: number; stage: string; stageMessage: string }> = {}

    backgroundTasks?.tasks.forEach((task) => {
      if (task.type !== "pdf_processing" || task.courseId !== courseId) {
        return
      }
      if (task.materialId.startsWith("upload-") || isFinalBackgroundTaskStatus(task.status)) {
        return
      }

      progressByMaterial[task.materialId] = {
        progress: task.progress,
        stage: task.stage ?? task.status,
        stageMessage: task.stageMessage ?? "Wird verarbeitet...",
      }
    })

    return progressByMaterial
  }, [backgroundTasks?.tasks, courseId])

  useEffect(() => {
    if (!backgroundTasks) {
      return
    }

    const currentTasks = backgroundTasks.tasks.filter(
      (task) => task.type === "pdf_processing" && task.courseId === courseId
    )
    const nextStatuses = new Map<string, string>()
    let shouldRefresh = false

    currentTasks.forEach((task) => {
      nextStatuses.set(task.id, task.status)
      const previousStatus = previousTaskStatusesRef.current.get(task.id)
      if (
        previousStatus &&
        previousStatus !== task.status &&
        isFinalBackgroundTaskStatus(task.status)
      ) {
        shouldRefresh = true
      }
    })

    previousTaskStatusesRef.current = nextStatuses

    if (shouldRefresh) {
      void refreshMaterials()
    }
  }, [backgroundTasks?.tasks, courseId, refreshMaterials])

  return (
    <div className="space-y-6">
      <section className="app-section">
        <div className="app-section__header">
          <div>
            <h3 className="app-section__title">Material hochladen</h3>
            <p className="app-section__description">
              Fuege neue PDFs hinzu und behalte laufende Verarbeitungsschritte in derselben Arbeitsflaeche im Blick.
            </p>
          </div>
        </div>
        <UploadSection
          courseId={courseId}
          userId={userId}
          courseName={courseName}
          onUploadSuccess={handleUploadSuccess}
        />
      </section>

      <section className="app-section">
        <div className="app-section__header">
          <div>
            <h3 className="app-section__title">Hochgeladene Materialien</h3>
            <p className="app-section__description">
              Dateien, Verarbeitungsstatus und Flashcard-Aktionen fuer diesen Kursraum.
              {isRefreshing ? " Die Liste wird gerade aktualisiert." : ""}
            </p>
          </div>
          <span className="app-subtle-chip">{materials.length} Dateien im Kurs</span>
        </div>
        <CourseMaterialsList
          materials={materials}
          courseId={courseId}
          userId={userId}
          onMaterialDeleted={refreshMaterials}
          materialProgress={materialProgress}
          deduplicateFlashcards={deduplicateFlashcards}
        />
      </section>
    </div>
  )
}
