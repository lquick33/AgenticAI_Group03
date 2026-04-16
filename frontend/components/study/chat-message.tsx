"use client"

import React from "react"
import dynamic from "next/dynamic"
import ReactMarkdown from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkMath from "remark-math"
import { Sparkles, User } from "lucide-react"

import { Loader } from "@/components/ui/loader"
import { Tool } from "@/components/ui/tool"
import type { ChatMessage as ChatMessageType, ToolCall } from "@/types"
import { cn } from "@/lib/utils"

const QuizComponent = dynamic(
  () => import("./quiz-component").then((mod) => mod.QuizComponent),
  {
    loading: () => <div className="p-4 text-center text-muted-foreground">Quiz wird geladen...</div>,
    ssr: false,
  }
)

type ChatRole = "user" | "assistant"
type QuizPayload = NonNullable<ChatMessageType["quiz"]>

interface ChatMessageProps {
  id: string
  role: ChatRole
  content: string
  isStreaming?: boolean
  toolCalls?: ToolCall[]
  showTools?: boolean
  quiz?: QuizPayload
  onQuizComplete?: (quizId: string, answers: Record<string, "A" | "B" | "C" | "D">) => void
  isQuizSubmitting?: boolean
}

export const ChatMessage = React.memo(function ChatMessage({
  id,
  role,
  content,
  isStreaming = false,
  toolCalls,
  showTools = false,
  quiz,
  onQuizComplete,
  isQuizSubmitting = false,
}: ChatMessageProps) {
  const contentString = content
  const showTypingIndicator = role === "assistant" && contentString.trim() === "" && isStreaming

  if (role === "user" && !contentString) return null

  const hasTools = showTools && toolCalls && toolCalls.length > 0
  const hasQuiz =
    role === "assistant" &&
    Boolean(
      quiz &&
        quiz.quiz_id &&
        quiz.topic &&
        Array.isArray(quiz.questions) &&
        quiz.questions.length > 0 &&
        quiz.questions.every(
          (question) => question.id && question.question && question.options && question.correct_answer
        )
    )

  const avatar =
    role === "assistant" ? (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50 border border-zinc-200 dark:border-zinc-700 shadow-sm">
        <Sparkles className="h-4 w-4" />
      </div>
    ) : (
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-[var(--app-border-soft)] bg-[var(--app-surface)] text-muted-foreground shadow-[var(--app-shadow-soft)]">
        <User className="h-4 w-4" />
      </div>
    )

  return (
    <div className={cn("flex items-start gap-3", role === "user" ? "justify-end" : "justify-start")}>
      {role === "assistant" ? avatar : null}

      <div className={cn("min-w-0 max-w-[46rem]", role === "user" ? "order-first" : undefined)}>
        {hasTools ? (
          <div className="mb-3 space-y-2">
            {toolCalls.map((toolCall) => (
              <Tool key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        ) : null}

        {hasQuiz && quiz ? (
          <div className="mb-4 rounded-[1.5rem] border border-[var(--app-border-soft)] bg-[var(--app-surface)] p-2 shadow-[var(--app-shadow-soft)]">
            <QuizComponent
              quizId={quiz.quiz_id}
              topic={quiz.topic}
              questions={quiz.questions}
              onComplete={onQuizComplete ?? ((_quizId, _answers) => {})}
              isSubmitting={isQuizSubmitting}
            />
          </div>
        ) : null}

        <div
          id={id}
          className={cn(
            "overflow-hidden rounded-2xl border px-5 py-4 shadow-sm",
            role === "assistant"
              ? "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
              : "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-foreground"
          )}
        >
          {showTypingIndicator ? (
            <div className="flex items-center gap-3">
              <Loader size={18} className="animate-spin text-[var(--app-accent)]" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Tutor denkt nach...</p>
                <p className={cn("text-xs", role === "assistant" ? "text-zinc-500" : "text-muted-foreground")}>
                  Die Antwort wird vorbereitet.
                </p>
              </div>
            </div>
          ) : (
            <div className="markdown-gemini max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  p: ({ children }) => <p>{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                  em: ({ children }) => <em className="italic">{children}</em>,
                  ul: ({ children }) => <ul className="ml-6 list-outside list-disc space-y-2">{children}</ul>,
                  ol: ({ children }) => <ol className="ml-6 list-outside list-decimal space-y-2">{children}</ol>,
                  li: ({ children }) => <li className="pl-2">{children}</li>,
                  code: ({ children, className }) => {
                    const isInline = !className?.includes("language-")
                    return isInline ? (
                      <code
                        className={cn(
                          "rounded px-1.5 py-0.5 text-xs font-mono",
                          role === "assistant"
                            ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                            : "bg-[var(--app-surface-subtle)] text-foreground"
                        )}
                      >
                        {children}
                      </code>
                    ) : (
                      <code className={className}>{children}</code>
                    )
                  },
                  pre: ({ children }) => (
                    <pre
                      className={cn(
                        "overflow-x-auto rounded-xl p-3 text-xs font-mono",
                        role === "assistant"
                            ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700"
                            : "bg-[var(--app-surface-subtle)] text-foreground"
                      )}
                    >
                      {children}
                    </pre>
                  ),
                  h1: ({ children }) => <h1 className="text-xl font-semibold">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-lg font-semibold">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-base font-semibold">{children}</h3>,
                  blockquote: ({ children }) => (
                    <blockquote
                      className={cn(
                        "my-0 border-l-4 pl-4 italic",
                          role === "assistant"
                            ? "border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300"
                            : "border-[var(--app-border-strong)] text-muted-foreground"
                      )}
                    >
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {contentString}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>

      {role === "user" ? avatar : null}
    </div>
  )
})

