"use client"

import { useEffect, useRef } from "react"

import { ConversationEmptyState } from "@/components/ai/conversation"
import { Loader } from "@/components/ui/loader"
import { Label } from "@/components/ui/label"
import type { ChatMessage as ChatMessageType } from "@/types"
import { ChatMessage } from "./chat-message"
import { TutorPromptInput } from "./tutor-prompt-input"
import { Tool } from "@/components/ui/tool"
import { BugIcon } from "lucide-react"

interface ChatInterfaceProps {
  messages: ChatMessageType[]
  onSend: (message: string) => void
  isLoading: boolean
  isStreaming?: boolean
  contextInfo?: string
  showTools?: boolean
  onToggleTools?: (enabled: boolean) => void
  onQuizComplete?: (quizId: string, answers: Record<string, "A" | "B" | "C" | "D">) => void
  submittingQuizId?: string | null
}

const NEAR_BOTTOM_THRESHOLD = 100

function isNearBottom(element: HTMLDivElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= NEAR_BOTTOM_THRESHOLD
}

export function ChatInterface({
  messages,
  onSend,
  isLoading,
  isStreaming = false,
  contextInfo,
  showTools = false,
  onToggleTools,
  onQuizComplete,
  submittingQuizId = null,
}: ChatInterfaceProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const shouldAutoScrollRef = useRef(true)
  const isInitiallyLoading = messages.length === 0 && (isLoading || isStreaming)

  useEffect(() => {
    const scrollElement = scrollRef.current
    if (!scrollElement) {
      return
    }

    const handleScroll = () => {
      shouldAutoScrollRef.current = isNearBottom(scrollElement)
    }

    shouldAutoScrollRef.current = isNearBottom(scrollElement)
    scrollElement.addEventListener("scroll", handleScroll, { passive: true })

    return () => {
      scrollElement.removeEventListener("scroll", handleScroll)
    }
  }, [])

  useEffect(() => {
    const scrollElement = scrollRef.current
    if (!scrollElement || !shouldAutoScrollRef.current) {
      return
    }

    scrollElement.scrollTo({
      top: scrollElement.scrollHeight,
      behavior: "auto",
    })
  }, [messages, isStreaming])

  return (
    <div className="flex h-full min-h-0 flex-col bg-transparent">
      {onToggleTools ? (
        <div className="absolute top-2 right-2 z-50">
          <button
            onClick={() => onToggleTools(!showTools)}
            className="flex h-8 w-8 items-center justify-center rounded-full text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300 transition-colors"
            title="Entwicklerwerkzeuge (Tool Calls)"
          >
            <BugIcon className="h-4 w-4" />
          </button>
        </div>
      ) : null}

      {showTools && (
        <div className="flex-shrink-0 border-b border-orange-200 bg-orange-50 dark:border-orange-900/50 dark:bg-orange-900/20 px-4 py-2 text-xs text-orange-800 dark:text-orange-400">
          Entwicklermodus aktiv: System-Tools und interne Schritte werden angezeigt.
        </div>
      )}

      {contextInfo ? (
        <div className="flex-shrink-0 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 px-4 py-2">
          <div className="text-[10px] uppercase tracking-widest text-zinc-500 font-semibold mb-0.5">
            Aktiver Kontext
          </div>
          <p className="min-w-0 truncate text-xs text-zinc-700 dark:text-zinc-300">
            {contextInfo}
          </p>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">
        <div ref={scrollRef} className="h-full overflow-y-auto px-4 py-5 lg:px-5">
          <div className="mx-auto flex max-w-[54rem] flex-col gap-5">
            {isInitiallyLoading ? (
              <div className="flex min-h-[260px] items-center justify-center">
                <div className="w-full max-w-md rounded-[1.75rem] border border-[var(--app-border-soft)] bg-[var(--app-surface)] px-6 py-5 text-center shadow-[var(--app-shadow-soft)]">
                  <div className="flex items-center justify-center gap-3 text-foreground">
                    <Loader size={20} className="animate-spin text-[var(--app-accent)]" />
                    <p className="text-sm font-medium">Tutor denkt nach...</p>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Die Antwort zu deinen aktuellen Folien wird vorbereitet.
                  </p>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="app-empty-state min-h-[260px]">
                <ConversationEmptyState
                  title="Noch keine Nachrichten"
                  description="Beginne eine Unterhaltung mit dem Tutor, um die aktuelle Seite erklaeren zu lassen."
                />
              </div>
            ) : (
              messages.map((message, index) => {
                const isLastMessage = index === messages.length - 1
                const messageContent = message.content
                const isStreamingMessage =
                  isLastMessage &&
                  message.role === "assistant" &&
                  (!messageContent || messageContent.trim() === "") &&
                  (message.id.startsWith("streaming-") || isStreaming)

                const quiz = message.quiz
                const isQuizSubmitting = quiz && submittingQuizId === quiz.quiz_id
                const handleQuizCompleteForMessage =
                  quiz && onQuizComplete
                    ? (quizId: string, answers: Record<string, "A" | "B" | "C" | "D">) => {
                        onQuizComplete(quizId, answers)
                      }
                    : undefined

                return (
                  <ChatMessage
                    key={message.id}
                    id={message.id}
                    role={message.role === "user" ? "user" : "assistant"}
                    content={messageContent}
                    isStreaming={isStreamingMessage}
                    toolCalls={message.toolCalls}
                    showTools={showTools}
                    quiz={quiz}
                    onQuizComplete={handleQuizCompleteForMessage}
                    isQuizSubmitting={isQuizSubmitting}
                  />
                )
              })
            )}
          </div>
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-[var(--app-border-soft)] bg-[var(--app-surface)] px-4 py-4 lg:px-5">
        <div className="mx-auto max-w-[54rem]">
          <TutorPromptInput
            onSubmit={onSend}
            isLoading={isLoading}
            isStreaming={isStreaming}
            contextInfo={contextInfo}
          />
        </div>
      </div>
    </div>
  )
}
