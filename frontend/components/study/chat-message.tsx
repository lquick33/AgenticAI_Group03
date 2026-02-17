"use client"

import React from "react"
import dynamic from "next/dynamic"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import { User } from "lucide-react"
import { Loader } from "@/components/ui/loader"
import { Tool } from "@/components/ui/tool"
import type { ChatMessage as ChatMessageType, ToolCall } from "@/types"

// OPTIMIZED: Lazy load QuizComponent since it's large and not always needed
const QuizComponent = dynamic(
  () => import("./quiz-component").then((mod) => mod.QuizComponent),
  { 
    loading: () => <div className="p-4 text-center text-muted-foreground">Quiz wird geladen...</div>,
    ssr: false 
  }
)

type ChatRole = "user" | "assistant"

interface ChatMessageProps {
  id: string
  role: ChatRole
  content: string
  isStreaming?: boolean
  toolCalls?: ToolCall[]
  showTools?: boolean
  quiz?: {
    quiz_id: string
    topic: string
    questions: Array<{
      id: string
      question: string
      options: Record<'A' | 'B' | 'C' | 'D', string>
      correct_answer: 'A' | 'B' | 'C' | 'D'
      difficulty: 'easy' | 'medium' | 'hard'
      explanation: string
    }>
  }
  onQuizComplete?: (answers: Record<string, 'A' | 'B' | 'C' | 'D'>) => void
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
  isQuizSubmitting = false
}: ChatMessageProps) {
  // Ensure content is always a string
  const contentString = typeof content === 'string' ? content : (content?.toString() || '')
  
  // Show typing indicator ONLY if there's no content yet (even during streaming, show content if available)
  const showTypingIndicator = role === "assistant" && (!contentString || contentString.trim() === "") && isStreaming
  
  if (role === "user" && !contentString) return null

  const hasTools = showTools && toolCalls && toolCalls.length > 0
  // Verbesserte Quiz-Validierung mit detaillierteren Checks
  const hasQuiz = role === "assistant" && 
    quiz && 
    quiz.quiz_id && 
    quiz.topic && 
    quiz.questions && 
    Array.isArray(quiz.questions) && 
    quiz.questions.length > 0 &&
    quiz.questions.every(q => q.id && q.question && q.options && q.correct_answer)

  return (
    <div
      className={cn(
        "flex items-start space-x-3",
        role === "user" ? "justify-end" : "justify-start"
      )}
    >
      {/* Avatar */}
      {role === "assistant" && (
        <div className="w-8 h-8 bg-black rounded-full flex items-center justify-center flex-shrink-0">
          <span className="text-white text-sm font-medium">H</span>
        </div>
      )}

      {/* Message Body */}
      <div
        className={cn(
          "flex-1 min-w-0",
          role === "user" && "order-first"
        )}
      >
        {/* Tool Calls - Dezente Anzeige vor der Message */}
        {hasTools && (
          <div className="mb-2 space-y-1">
            {toolCalls.map((toolCall) => (
              <Tool key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}
        
        {/* Quiz Component - Render below message content if present */}
        {hasQuiz && (
          <div className="mb-4">
            <QuizComponent
              quizId={quiz!.quiz_id}
              topic={quiz!.topic}
              questions={quiz!.questions}
              onComplete={onQuizComplete || (() => {})}
              isSubmitting={isQuizSubmitting}
            />
          </div>
        )}
        
        <div
          className={cn(
            "rounded-2xl px-5 py-4",
            role === "assistant"
              ? "bg-black text-white"
              : "bg-gray-100 text-gray-900"
          )}
        >
          {showTypingIndicator ? (
            <div className="flex items-center gap-3">
              <Loader size={18} className="text-white animate-spin" />
              <div className="space-y-1">
                <p className="text-sm font-medium">Tutor denkt nach...</p>
                <p className="text-xs text-white/70">
                  Die Antwort wird vorbereitet.
                </p>
              </div>
            </div>
          ) : (
            <div className="markdown-gemini max-w-none min-w-0">
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  p: ({ children }) => (
                    <p>{children}</p>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold">
                      {children}
                    </strong>
                  ),
                  em: ({ children }) => (
                    <em className="italic">
                      {children}
                    </em>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-outside space-y-2 ml-6">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-outside space-y-2 ml-6">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="pl-2">{children}</li>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className?.includes("language-")
                    return isInline ? (
                      <code
                        className={cn(
                          "px-1 py-0.5 rounded text-xs font-mono whitespace-pre-wrap break-words",
                          role === "assistant"
                            ? "bg-white/10 text-white"
                            : "bg-gray-200 text-gray-900"
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
                        "p-2 rounded text-xs font-mono max-w-full overflow-x-hidden whitespace-pre-wrap break-words",
                        role === "assistant"
                          ? "bg-white/10 text-white"
                          : "bg-gray-200 text-gray-900"
                      )}
                    >
                      {children}
                    </pre>
                  ),
                  h1: ({ children }) => (
                    <h1 className="text-xl font-semibold">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-semibold">{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-semibold">{children}</h3>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote
                      className={cn(
                        "border-l-4 pl-4 italic my-0",
                        role === "assistant"
                          ? "border-white/30 text-white/90"
                          : "border-gray-300 text-gray-700"
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

      {/* Avatar */}
      {role === "user" && (
        <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-gray-600" />
        </div>
      )}
    </div>
  )
})
