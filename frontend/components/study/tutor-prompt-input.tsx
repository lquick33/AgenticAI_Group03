"use client"

import { useRef, useState } from "react"

import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from "./prompt-input"
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
  placeholder = "Stelle Fragen zu den Folien oder bitte um eine kurze Erklaerung...",
  contextInfo,
}: TutorPromptInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [inputValue, setInputValue] = useState("")

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (inputValue.trim() && !isLoading) {
      onSubmit(inputValue.trim())
      setInputValue("")
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
    <div className="w-full relative">

      <PromptInput
        onSubmit={handleSubmit}
        className="rounded-[1.5rem] border-[var(--app-border-soft)] bg-[var(--app-surface)] shadow-[var(--app-shadow-soft)]"
      >
        <PromptInputTextarea
          ref={textareaRef}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
          onEnter={handleEnter}
          className="px-4 py-4"
        />
        <PromptInputToolbar className="absolute right-2 bottom-2 pt-0 pb-0">
          <PromptInputTools className="hidden"><></></PromptInputTools>
          <PromptInputSubmit
            status={getStatus()}
            disabled={isLoading || !inputValue.trim()}
            variant="accent"
            size="icon-touch"
            aria-label="Nachricht senden"
          />
        </PromptInputToolbar>
      </PromptInput>


    </div>
  )
}
