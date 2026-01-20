"use client"

import { useRef } from 'react'
import { ConversationEmptyState } from '@/components/ai/conversation'
import { ChatMessage } from './chat-message'
import { TutorPromptInput } from './tutor-prompt-input'
import type { ChatMessage as ChatMessageType } from '@/types'

interface ChatInterfaceProps {
  messages: ChatMessageType[]
  onSend: (message: string) => void
  isLoading: boolean
  isStreaming?: boolean
  contextInfo?: string
}

export function ChatInterface({
  messages,
  onSend,
  isLoading,
  isStreaming = false,
  contextInfo,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  return (
    <div className="flex flex-col h-full min-h-0 bg-[#f6f4f1]">
      {/* Optional Context Banner */}
      {contextInfo && (
        <div className="bg-blue-50 border-b border-blue-200 p-4 flex-shrink-0">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <span className="text-sm font-medium text-blue-900">Kontext:</span>
              <span className="text-sm text-blue-700">{contextInfo}</span>
            </div>
            <button
              type="button"
              className="text-xs text-blue-600 hover:text-blue-800 p-0 h-auto flex items-center gap-1"
            >
              <span className="w-3 h-3">×</span>
              <span>Kontext entfernen</span>
            </button>
          </div>
        </div>
      )}

      {/* Conversation Container */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <div
          ref={scrollRef}
          className="h-full overflow-y-auto px-4 py-4 space-y-6"
        >
          {messages.length === 0 ? (
            <ConversationEmptyState
              title="Noch keine Nachrichten"
              description="Beginne eine Unterhaltung mit dem Tutor"
            />
          ) : (
            messages.map((message, index) => (
              <div key={message.id} className={index > 0 ? "mt-6" : ""}>
                <ChatMessage
                  id={message.id}
                  role={message.role}
                  content={message.content}
                />
              </div>
            ))
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white flex-shrink-0">
        <TutorPromptInput
          onSubmit={onSend}
          isLoading={isLoading}
          isStreaming={isStreaming}
          contextInfo={contextInfo}
        />
      </div>
    </div>
  )
}
