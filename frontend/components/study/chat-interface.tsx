"use client"

import { useRef } from 'react'
import { ConversationEmptyState } from '@/components/ai/conversation'
import { Loader } from '@/components/ui/loader'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { ChatMessage } from './chat-message'
import { TutorPromptInput } from './tutor-prompt-input'
import type { ChatMessage as ChatMessageType } from '@/types'

interface ChatInterfaceProps {
  messages: ChatMessageType[]
  onSend: (message: string) => void
  isLoading: boolean
  isStreaming?: boolean
  contextInfo?: string
  showTools?: boolean
  onToggleTools?: (enabled: boolean) => void
}

export function ChatInterface({
  messages,
  onSend,
  isLoading,
  isStreaming = false,
  contextInfo,
  showTools = false,
  onToggleTools,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const isInitiallyLoading = messages.length === 0 && (isLoading || isStreaming)

  return (
    <div className="flex flex-col h-full w-full min-h-0 bg-[#f6f4f1]">
      {/* Tool Toggle Switch - Dezente Position oben rechts */}
      {onToggleTools && (
        <div className="flex items-center justify-end gap-2 px-4 pt-3 pb-2 flex-shrink-0">
          <Label htmlFor="show-tools" className="text-xs text-muted-foreground cursor-pointer">
            Tools anzeigen
          </Label>
          <Switch
            id="show-tools"
            checked={showTools}
            onCheckedChange={onToggleTools}
          />
        </div>
      )}

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
            // Vollflächiger Ladezustand beim Initialisieren der Sitzung
            <div className="flex h-full items-center justify-center">
              <div className="flex flex-col items-center gap-3 rounded-2xl bg-black text-white px-6 py-4 max-w-md w-full">
                <div className="flex items-center gap-3">
                  <Loader size={20} className="animate-spin" />
                  <p className="text-sm font-medium">Tutor denkt nach...</p>
                </div>
                <p className="text-xs text-white/70 text-center">
                  Die Antwort zu deinen aktuellen Folien wird vorbereitet.
                </p>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <ConversationEmptyState
              title="Noch keine Nachrichten"
              description="Beginne eine Unterhaltung mit dem Tutor"
            />
          ) : (
            messages.map((message, index) => {
              // Check if this is the last message and it's streaming
              const isLastMessage = index === messages.length - 1
              const isStreamingMessage = isLastMessage && isStreaming && message.role === "assistant" && (!message.content || message.content.trim() === "")
              
              return (
                <div key={message.id} className={index > 0 ? "mt-6" : ""}>
                  <ChatMessage
                    id={message.id}
                    role={message.role}
                    content={message.content}
                    isStreaming={isStreamingMessage}
                    toolCalls={message.toolCalls}
                    showTools={showTools}
                  />
                </div>
              )
            })
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
