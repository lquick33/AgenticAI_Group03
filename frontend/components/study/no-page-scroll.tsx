"use client"

import { useEffect } from 'react'

/**
 * Component that prevents page scrolling by adding a class to html/body
 * Only use this on pages where page-level scrolling should be disabled
 * (e.g., StudyReader page)
 */
export function NoPageScroll() {
  useEffect(() => {
    // Add class to body to prevent page-level scrolling
    // Only body needs the class, html doesn't need it
    document.body.classList.add('no-page-scroll')

    // Cleanup: remove class when component unmounts
    return () => {
      document.body.classList.remove('no-page-scroll')
    }
  }, [])

  return null
}
