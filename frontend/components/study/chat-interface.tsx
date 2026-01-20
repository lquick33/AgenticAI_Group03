"use client"

import { useRef } from 'react'
import { ConversationEmptyState } from '@/components/ai/conversation'
import { Loader } from '@/components/ui/loader'
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

  const isInitiallyLoading = messages.length === 0 && (isLoading || isStreaming)

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
          {isInitiallyLoading ? (
            <div className="flex h-full items-center">
              <div className="flex items-start space-x-3 justify-start">
                {/* Avatar wie beim Tutor */}
                <div className="w-8 h-8 bg-black rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-white text-sm font-medium">H</span>
                </div>

                {/* „Nachrichten“-Bubble im gleichen Layout wie ChatMessage */}
                <div className="flex-1 max-w-[80%]">
                  <div className="rounded-2xl px-4 py-3 bg-black text-white">
                    <div className="flex items-center gap-3">
                      <Loader size={18} className="text-white" />
                      <div className="space-y-1">
                        <p className="text-sm font-medium">Tutor lädt …</p>
                        <p className="text-xs text-white/70">
                          Die erste Nachricht wird vorbereitet.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : messages.length === 0 ? (
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
