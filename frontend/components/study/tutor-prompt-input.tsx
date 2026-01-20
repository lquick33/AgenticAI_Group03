"use client"

import { useRef, useState } from "react"
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
  PromptInputButton,
  PromptInputSubmit,
} from "./prompt-input"
import { Paperclip, Mic } from "lucide-react"
import type { SubmitStatus } from "./prompt-input"

interface TutorPromptInputProps {
  onSubmit: (message: string) => void
  isLoading?: boolean
  isStreaming?: boolean
  placeholder?: string
  contextInfo?: string
}

export function TutorPromptInput({
  onSubmit,
  isLoading = false,
  isStreaming = false,
  placeholder = "Stellen Sie Fragen zu den Folien oder zum Lernstoff...",
  contextInfo,
}: TutorPromptInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [inputValue, setInputValue] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim() && !isLoading) {
      onSubmit(inputValue.trim())
      setInputValue("")
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto"
      }
    }
  }

  const handleEnter = () => {
    if (inputValue.trim() && !isLoading) {
      handleSubmit({ preventDefault: () => {} } as React.FormEvent)
    }
  }

  const getStatus = (): SubmitStatus => {
    if (isStreaming) return "streaming"
    if (isLoading) return "submitted"
    return "ready"
  }

  return (
    <div className="w-full">
      {/* Status Bar */}
      <div className="flex items-center justify-between mb-2 px-1">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full" />
          <span className="text-sm text-gray-600">🧠 Tutor-Agent aktiv</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-sm font-medium text-gray-700">Lerntutor bereit</span>
        </div>
      </div>

      {/* Prompt Input */}
      <PromptInput onSubmit={handleSubmit}>
        <PromptInputTextarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
          onEnter={handleEnter}
        />
        <PromptInputToolbar>
          <PromptInputTools>
            <PromptInputButton type="button" size="sm">
              <Paperclip className="size-4" />
            </PromptInputButton>
            <PromptInputButton type="button" size="sm">
              <Mic className="size-4" />
              <span>Voice</span>
            </PromptInputButton>
          </PromptInputTools>
          <PromptInputSubmit
            status={getStatus()}
            disabled={isLoading || !inputValue.trim()}
          />
        </PromptInputToolbar>
      </PromptInput>

      {/* Context Info */}
      {contextInfo && (
        <div className="text-xs text-gray-500 mt-2 px-1">
          <span className="font-medium">Kontext: </span>
          {contextInfo}
        </div>
      )}
    </div>
  )
}
