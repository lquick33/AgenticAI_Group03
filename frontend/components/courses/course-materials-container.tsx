"use client"

import { useState, useEffect, useCallback, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'
import { UploadSection } from '@/components/courses/upload-section'
import { CourseMaterialsList } from '@/components/courses/course-materials-list'
import type { CourseMaterial } from '@/types'

interface CourseMaterialsContainerProps {
  courseId: string
  userId: string
  initialMaterials: CourseMaterial[]
}

export function CourseMaterialsContainer({
  courseId,
  userId,
  initialMaterials,
}: CourseMaterialsContainerProps) {
  const [materials, setMaterials] = useState<CourseMaterial[]>(initialMaterials)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [pollingCount, setPollingCount] = useState(0) // Track count to trigger polling effect
  
  // Refs to track materials being polled without causing effect re-runs
  const materialsRef = useRef<CourseMaterial[]>(initialMaterials)
  const pollingMaterialsRef = useRef<Map<string, { id: string; initialFilename: string }>>(new Map())
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Update materials when initialMaterials prop changes (e.g., from server-side fetch)
  useEffect(() => {
    setMaterials(initialMaterials)
    materialsRef.current = initialMaterials
  }, [initialMaterials])

  // Update ref when materials state changes and manage polling map
  useEffect(() => {
    materialsRef.current = materials
    
    // Update polling materials map based on current materials
    const currentProcessing = materials.filter(m => 
      m.processing_status === 'processing' || m.processing_status === 'uploading'
    )
    
    let mapChanged = false
    
    // Add new processing materials to polling map
    currentProcessing.forEach(m => {
      if (!pollingMaterialsRef.current.has(m.id)) {
        pollingMaterialsRef.current.set(m.id, {
          id: m.id,
          initialFilename: m.file_name
        })
        mapChanged = true
      }
    })
    
    // Remove materials that are no longer processing
    const processingIds = new Set(currentProcessing.map(m => m.id))
    for (const [id] of pollingMaterialsRef.current) {
      if (!processingIds.has(id)) {
        pollingMaterialsRef.current.delete(id)
        mapChanged = true
      }
    }
    
    // Update polling count to trigger polling effect restart if needed
    if (mapChanged) {
      setPollingCount(pollingMaterialsRef.current.size)
    }
  }, [materials])

  const refreshMaterials = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const supabase = createClient()
      const { data, error } = await supabase
        .from('course_materials')
        .select('*')
        .eq('course_id', courseId)
        .order('created_at', { ascending: false })

      if (error) {
        console.error('Error refreshing materials:', error)
        // Don't throw - keep existing materials on error
        return
      }

      if (data) {
        setMaterials(data as CourseMaterial[])
      }
    } catch (error) {
      console.error('Error refreshing materials:', error)
      // Don't throw - keep existing materials on error
    } finally {
      setIsRefreshing(false)
    }
  }, [courseId])

  const handleUploadSuccess = useCallback(() => {
    // Refresh materials after a short delay to ensure database transaction is committed
    // The material is already in the database, but a small delay ensures consistency
    setTimeout(() => {
      refreshMaterials()
    }, 300)
  }, [refreshMaterials])

  // Poll for filename updates on materials that are processing
  useEffect(() => {
    // Clear any existing polling interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    
    // Start polling if there are materials to poll
    if (pollingMaterialsRef.current.size === 0) {
      return
    }
    
    const pollInterval = setInterval(async () => {
      const supabase = createClient()
      const pollingMaterials = Array.from(pollingMaterialsRef.current.values())
      
      for (const { id, initialFilename } of pollingMaterials) {
        try {
          const { data, error } = await supabase
            .from('course_materials')
            .select('file_name, processing_status')
            .eq('id', id)
            .single()
          
          if (error) {
            console.error(`Error polling material ${id}:`, error)
            continue
          }
          
          if (data) {
            // Get current material from ref
            const currentMaterial = materialsRef.current.find(m => m.id === id)
            
            // Check if filename changed (compare with both initial and current)
            const filenameChanged = data.file_name !== initialFilename && 
                                   (!currentMaterial || data.file_name !== currentMaterial.file_name)
            
            if (filenameChanged) {
              // Update the initial filename in the ref to prevent duplicate updates
              pollingMaterialsRef.current.set(id, {
                id,
                initialFilename: data.file_name
              })
              
              // Immediately refresh materials to get the updated filename
              refreshMaterials()
              
              // If processing is complete, remove from polling
              if (data.processing_status !== 'processing' && data.processing_status !== 'uploading') {
                pollingMaterialsRef.current.delete(id)
                setPollingCount(pollingMaterialsRef.current.size)
              }
            } else if (data.processing_status !== 'processing' && data.processing_status !== 'uploading') {
              // Processing complete, remove from polling
              pollingMaterialsRef.current.delete(id)
              setPollingCount(pollingMaterialsRef.current.size)
            }
          }
        } catch (error) {
          console.error(`Error polling material ${id}:`, error)
        }
      }
      
      // Clean up polling if no materials left to poll
      if (pollingMaterialsRef.current.size === 0) {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }
        setPollingCount(0)
      }
    }, 2000) // Poll every 2 seconds
    
    pollIntervalRef.current = pollInterval
    
    // Cleanup after 5 minutes or when component unmounts (increased timeout for filename generation)
    const timeout = setTimeout(() => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      pollingMaterialsRef.current.clear()
      setPollingCount(0)
    }, 300000) // 5 minutes
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      clearTimeout(timeout)
    }
  }, [refreshMaterials, pollingCount]) // Include pollingCount to restart when materials are added/removed

  return (
    <>
      <div className="px-4 lg:px-6">
        <UploadSection 
          courseId={courseId} 
          userId={userId}
          onUploadSuccess={handleUploadSuccess}
        />
      </div>
      <div className="px-4 lg:px-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Hochgeladene Materialien</h2>
          <p className="text-sm text-muted-foreground">
            Übersicht aller hochgeladenen Vorlesungsmaterialien
          </p>
        </div>
        <CourseMaterialsList 
          materials={materials}
          courseId={courseId}
          userId={userId}
        />
      </div>
    </>
  )
}
