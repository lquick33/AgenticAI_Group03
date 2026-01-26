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
   * @returns Array of tool response events that can now be processed (retryable)
   */
  add(event: ToolResponseEvent): ToolResponseEvent[] {
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
      
      // WICHTIG: Versuche pending tool responses zu verarbeiten
      // wenn ein neuer tool_call hinzugefügt wurde
      const retryable = this.retryPendingToolResponses()
      if (retryable.length > 0) {
        console.log(
          `[EventQueue] ${retryable.length} pending tool responses can now be processed`
        )
        // WICHTIG: Gib diese Events zurück, damit der Caller sie sofort verarbeiten kann
        return retryable
      }
    }
    
    // Keine retryable Events
    return []
  }

  /**
   * Validate event order: tool_call should come before tool_response
   */
  validateOrder(event: ToolResponseEvent): boolean {
    if (event.type === 'tool_response' && event.tool_call_id) {
      // Prüfe ob wir den entsprechenden tool_call bereits gesehen haben
      const hasToolCall = this.toolCallIds.has(event.tool_call_id)
      
      if (!hasToolCall) {
        console.warn(
          `[EventQueue] Tool response received before tool call: ${event.tool_call_id}`,
          'This event will be queued and retried'
        )
        return false
      }
      
      return true
    }
    
    // Tool calls sind immer erlaubt
    if (event.type === 'tool_call') {
      return true
    }
    
    // Andere Event-Typen sind immer erlaubt
    return true
  }

  /**
   * Check if a tool response can be processed (corresponding tool call exists)
   */
  canProcessToolResponse(toolCallId: string): boolean {
    return this.toolCallIds.has(toolCallId)
  }

  /**
   * Get pending tool responses waiting for their tool calls
   */
  getPendingToolResponses(): QueuedEvent[] {
    return this.queue.filter(e => 
      !e.processed && 
      e.event.type === 'tool_response' &&
      e.event.tool_call_id &&
      !this.toolCallIds.has(e.event.tool_call_id)
    )
  }

  /**
   * Retry processing pending tool responses (call after new tool_call added)
   */
  retryPendingToolResponses(): ToolResponseEvent[] {
    const pending = this.getPendingToolResponses()
    const now = Date.now()
    const maxWaitTime = 5000 // 5 Sekunden Timeout
    const retryable: ToolResponseEvent[] = []
    
    for (const queued of pending) {
      const waitTime = now - queued.timestamp
      
      // Timeout: Event wartet zu lange
      if (waitTime > maxWaitTime) {
        console.warn(
          `[EventQueue] Tool response timed out after ${waitTime}ms:`,
          queued.event.tool_call_id
        )
        queued.processed = true // Markiere als verarbeitet (fehlgeschlagen)
        continue
      }
      
      // Prüfe ob Tool Call jetzt verfügbar ist
      if (queued.event.tool_call_id && 
          this.toolCallIds.has(queued.event.tool_call_id)) {
        retryable.push(queued.event)
        queued.processed = true
      }
    }
    
    return retryable
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
