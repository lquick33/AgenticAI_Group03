/**
 * Progress calculation utilities for PDF processing
 */

export interface ProcessingProgressData {
  status: 'uploading' | 'processing' | 'completed' | 'error'
  completedPages: number
  totalPages: number
  hasSummary: boolean
  hasClassification: boolean
}

export interface ProcessingProgressResult {
  progress: number
  stage: string
  stageMessage: string
}

/**
 * Calculate processing progress percentage based on all stages of PDF processing
 * 
 * Stages:
 * - 0-5%: File upload
 * - 5-85%: Page analysis (based on completed pages)
 * - 85-90%: Summary generation (when summary field exists)
 * - 90-95%: Classification (when classification field exists)
 * - 95-100%: Finalization
 * - 100%: Only when status is 'completed'
 */
export function calculateProcessingProgress(
  data: ProcessingProgressData
): ProcessingProgressResult {
  const {
    status,
    completedPages,
    totalPages,
    hasSummary,
    hasClassification,
  } = data

  // Uploading stage
  if (status === 'uploading') {
    return {
      progress: 5,
      stage: 'uploading',
      stageMessage: 'Wird hochgeladen...',
    }
  }

  // Error state
  if (status === 'error') {
    return {
      progress: 0,
      stage: 'error',
      stageMessage: 'Fehler aufgetreten',
    }
  }

  // Completed state - always 100%
  if (status === 'completed') {
    return {
      progress: 100,
      stage: 'completed',
      stageMessage: 'Fertig',
    }
  }

  // Processing state - calculate based on current stage
  if (status === 'processing') {
    // Page analysis stage: 5-85%
    if (totalPages > 0 && completedPages < totalPages) {
      const pageProgress = 5 + (completedPages / totalPages) * 80
      return {
        progress: Math.min(Math.round(pageProgress), 85),
        stage: 'analyzing',
        stageMessage: `Seite ${completedPages} von ${totalPages} wird analysiert...`,
      }
    }

    // All pages done - check post-processing stages
    if (totalPages > 0 && completedPages >= totalPages) {
      // Summary generation: 85-90%
      if (!hasSummary) {
        return {
          progress: 85,
          stage: 'summarizing',
          stageMessage: 'Zusammenfassung wird erstellt...',
        }
      }

      // Classification: 90-95%
      if (!hasClassification) {
        return {
          progress: 90,
          stage: 'classifying',
          stageMessage: 'Material wird klassifiziert...',
        }
      }

      // Finalization: 95-99% (still processing means finalizing)
      return {
        progress: 95,
        stage: 'finalizing',
        stageMessage: 'Wird finalisiert...',
      }
    }

    // Edge case: no pages or unknown state
    return {
      progress: 5,
      stage: 'processing',
      stageMessage: 'Wird verarbeitet...',
    }
  }

  // Default fallback
  return {
    progress: 0,
    stage: 'unknown',
    stageMessage: 'Unbekannter Status',
  }
}
