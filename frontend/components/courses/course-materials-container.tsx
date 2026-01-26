"use client"

import { useState, useEffect, useCallback } from 'react'
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

  // Update materials when initialMaterials prop changes (e.g., from server-side fetch)
  useEffect(() => {
    setMaterials(initialMaterials)
  }, [initialMaterials])

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
    const processingMaterials = materials.filter(m => 
      m.processing_status === 'processing' || m.processing_status === 'uploading'
    )
    
    if (processingMaterials.length === 0) return
    
    const pollInterval = setInterval(async () => {
      const supabase = createClient()
      let hasUpdates = false
      
      for (const material of processingMaterials) {
        try {
          const { data, error } = await supabase
            .from('course_materials')
            .select('file_name, processing_status')
            .eq('id', material.id)
            .single()
          
          if (error) {
            console.error(`Error polling material ${material.id}:`, error)
            continue
          }
          
          if (data) {
            // Check if filename changed
            if (data.file_name !== material.file_name) {
              hasUpdates = true
              setMaterials(prev => prev.map(m => 
                m.id === material.id 
                  ? { ...m, file_name: data.file_name }
                  : m
              ))
            }
            
            // Update status if changed
            if (data.processing_status !== material.processing_status) {
              hasUpdates = true
              setMaterials(prev => prev.map(m => 
                m.id === material.id 
                  ? { ...m, processing_status: data.processing_status }
                  : m
              ))
            }
          }
        } catch (error) {
          console.error(`Error polling material ${material.id}:`, error)
        }
      }
      
      // If we got updates, refresh full materials list to ensure consistency
      if (hasUpdates) {
        refreshMaterials()
      }
    }, 2000) // Poll every 2 seconds
    
    // Cleanup after 60 seconds or when component unmounts
    const timeout = setTimeout(() => {
      clearInterval(pollInterval)
    }, 60000)
    
    return () => {
      clearInterval(pollInterval)
      clearTimeout(timeout)
    }
  }, [materials, refreshMaterials])

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
