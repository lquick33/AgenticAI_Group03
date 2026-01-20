"use client"

import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import { User } from "lucide-react"
import { Loader } from "@/components/ui/loader"
import type { ChatMessage as ChatMessageType } from "@/types"

type ChatRole = "user" | "assistant"

interface ChatMessageProps {
  id: string
  role: ChatRole
  content: string
  isStreaming?: boolean
}

export function ChatMessage({ id, role, content, isStreaming = false }: ChatMessageProps) {
  // Show typing indicator for assistant messages with empty content or streaming state
  const showTypingIndicator = role === "assistant" && (!content || content.trim() === "" || isStreaming)
  
  if (role === "user" && !content) return null

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
          "flex-1",
          role === "user" && "order-first"
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-3",
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
            <div className="text-sm leading-relaxed prose prose-sm max-w-none">
              <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong
                    className={cn(
                      "font-semibold",
                      role === "assistant" ? "text-white" : "text-gray-900"
                    )}
                  >
                    {children}
                  </strong>
                ),
                em: ({ children }) => (
                  <em
                    className={cn(
                      "italic",
                      role === "assistant" ? "text-white" : ""
                    )}
                  >
                    {children}
                  </em>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-sm">{children}</li>
                ),
                code: ({ children, className }) => {
                  const isInline = !className?.includes("language-")
                  return isInline ? (
                    <code
                      className={cn(
                        "px-1 py-0.5 rounded text-xs font-mono",
                        role === "assistant"
                          ? "bg-white/20 text-white"
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
                      "p-2 rounded text-xs font-mono overflow-x-auto",
                      role === "assistant"
                        ? "bg-white/20 text-white"
                        : "bg-gray-200 text-gray-900"
                    )}
                  >
                    {children}
                  </pre>
                ),
                h1: ({ children }) => (
                  <h1 className="text-lg font-semibold mb-2">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-base font-semibold mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-semibold mb-2">{children}</h3>
                ),
                blockquote: ({ children }) => (
                  <blockquote
                    className={cn(
                      "border-l-4 pl-3 italic",
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
              {content}
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
}
