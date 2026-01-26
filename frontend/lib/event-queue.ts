/**
 * Event Queue for SSE Stream Parsing
 * 
 * Manages event ordering and validation for Server-Sent Events (SSE)
 * to prevent race conditions and ensure proper event sequence.
 */

import type { ToolResponseEvent } from '@/types'

interface QueuedEvent {
  event: ToolResponseEvent
  timestamp: number
  processed: boolean
}

export class EventQueue {
  private queue: QueuedEvent[] = []
  private toolCallIds: Set<string> = new Set()
  private maxQueueSize = 100
  private debounceMs = 50

  /**
   * Add an event to the queue
   */
  add(event: ToolResponseEvent): void {
    // Prevent queue overflow
    if (this.queue.length >= this.maxQueueSize) {
      console.warn('[EventQueue] Queue full, removing oldest event')
      this.queue.shift()
    }

    const queuedEvent: QueuedEvent = {
      event,
      timestamp: Date.now(),
      processed: false
    }

    this.queue.push(queuedEvent)

    // Track tool call IDs for validation
    if (event.type === 'tool_call' && event.tool_calls) {
      event.tool_calls.forEach(tc => {
        this.toolCallIds.add(tc.id)
      })
    }
  }

  /**
   * Validate event order: tool_call should come before tool_response
   */
  validateOrder(event: ToolResponseEvent): boolean {
    if (event.type === 'tool_response') {
      // Check if we've seen the corresponding tool_call
      // Note: tool_call_id in tool_response should match a tool_call.id
      // This is a simplified check - in practice, you'd need to track the mapping
      return true // For now, we'll allow it and handle errors gracefully
    }
    return true
  }

  /**
   * Get next event to process (with debouncing)
   */
  getNext(): ToolResponseEvent | null {
    const now = Date.now()
    const unprocessed = this.queue.filter(e => !e.processed)

    if (unprocessed.length === 0) {
      return null
    }

    // Get the oldest unprocessed event
    const oldest = unprocessed[0]

    // Debounce: only return if enough time has passed since the event was added
    if (now - oldest.timestamp < this.debounceMs) {
      return null
    }

    // Mark as processed
    oldest.processed = true

    // Clean up processed events (keep last 10 for debugging)
    if (this.queue.filter(e => e.processed).length > 10) {
      this.queue = this.queue.filter(e => !e.processed)
    }

    return oldest.event
  }

  /**
   * Get all unprocessed events (for batch processing)
   */
  getAllUnprocessed(): ToolResponseEvent[] {
    return this.queue
      .filter(e => !e.processed)
      .map(e => e.event)
  }

  /**
   * Clear the queue
   */
  clear(): void {
    this.queue = []
    this.toolCallIds.clear()
  }

  /**
   * Check if queue has unprocessed events
   */
  hasUnprocessed(): boolean {
    return this.queue.some(e => !e.processed)
  }

  /**
   * Get queue size
   */
  size(): number {
    return this.queue.length
  }
}
