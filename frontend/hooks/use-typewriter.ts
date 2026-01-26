import { useRef, useCallback, useEffect } from 'react'
import type { ChatMessage } from '@/types'

export function useTypewriter(
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
) {
  const typewriterRef = useRef<{
    intervalId: NodeJS.Timeout | null
    fullText: string
    currentIndex: number
    messageId: string | null
  }>({
    intervalId: null,
    fullText: '',
    currentIndex: 0,
    messageId: null,
  })

  const stopTypewriter = useCallback(() => {
    if (typewriterRef.current.intervalId) {
      clearInterval(typewriterRef.current.intervalId)
      typewriterRef.current.intervalId = null
    }
    typewriterRef.current.fullText = ''
    typewriterRef.current.currentIndex = 0
    typewriterRef.current.messageId = null
  }, [])

  const startTypewriter = useCallback((fullText: string, messageId: string, speed: number = 40) => {
    // If typewriter is already running for this message, just update the fullText
    if (typewriterRef.current.messageId === messageId && typewriterRef.current.intervalId) {
      // Extend the fullText if new content is longer
      if (fullText.length > typewriterRef.current.fullText.length) {
        typewriterRef.current.fullText = fullText
        console.log('[useTypewriter] Extended typewriter text, new length:', fullText.length)
      }
      return
    }

    // Stop any existing typewriter
    stopTypewriter()

    // Initialize typewriter state
    typewriterRef.current.fullText = fullText
    typewriterRef.current.currentIndex = 0
    typewriterRef.current.messageId = messageId

    console.log('[useTypewriter] Starting typewriter animation, text length:', fullText.length, 'speed:', speed, 'ms per char')

    // Start animation
    typewriterRef.current.intervalId = setInterval(() => {
      const { fullText, currentIndex, messageId: msgId } = typewriterRef.current

      if (currentIndex >= fullText.length) {
        // Animation complete
        console.log('[useTypewriter] Typewriter animation complete')
        stopTypewriter()
        return
      }

      // Increment index (show 1 character at a time for smoother, more visible effect)
      const charsPerStep = 1
      typewriterRef.current.currentIndex += charsPerStep

      // Update message content
      setMessages((prev) => {
        const index = prev.findIndex((m) => m.id === msgId)
        if (index >= 0) {
          const updated = [...prev]
          updated[index] = {
            ...updated[index],
            content: fullText.slice(0, typewriterRef.current.currentIndex),
          }
          return updated
        }
        return prev
      })
    }, speed)
  }, [stopTypewriter, setMessages])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTypewriter()
    }
  }, [stopTypewriter])

  return {
    startTypewriter,
    stopTypewriter,
    typewriterRef
  }
}
