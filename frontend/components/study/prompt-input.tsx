"use client"

import { forwardRef, type ComponentProps, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { Send, Square, X, Paperclip, Mic, Loader2 } from "lucide-react"
import { Loader } from "@/components/ui/loader"

// PromptInput - Main form wrapper
interface PromptInputProps extends ComponentProps<"form"> {
  children: React.ReactNode
}

export function PromptInput({ className, children, ...props }: PromptInputProps) {
  return (
    <form
      className={cn(
        "w-full divide-y overflow-hidden rounded-xl border bg-background shadow-sm",
        className
      )}
      {...props}
    >
      {children}
    </form>
  )
}

// PromptInputTextarea
interface PromptInputTextareaProps extends ComponentProps<typeof Textarea> {
  onEnter?: () => void
}

export const PromptInputTextarea = forwardRef<
  HTMLTextAreaElement,
  PromptInputTextareaProps
>(({ className, onEnter, onKeyDown, ...props }, ref) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onEnter?.()
    }
    onKeyDown?.(e)
  }

  return (
    <Textarea
      ref={ref}
      className={cn(
        "w-full resize-none rounded-none border-none p-3 shadow-none outline-none ring-0 field-sizing-content max-h-[6lh] bg-transparent focus-visible:ring-0",
        className
      )}
      onKeyDown={handleKeyDown}
      {...props}
    />
  )
})

PromptInputTextarea.displayName = "PromptInputTextarea"

// PromptInputToolbar
interface PromptInputToolbarProps extends ComponentProps<"div"> {
  children: React.ReactNode
}

export function PromptInputToolbar({
  className,
  children,
  ...props
}: PromptInputToolbarProps) {
  return (
    <div
      className={cn("flex items-center justify-between p-1", className)}
      {...props}
    >
      {children}
    </div>
  )
}

// PromptInputTools
interface PromptInputToolsProps extends ComponentProps<"div"> {
  children: React.ReactNode
}

export function PromptInputTools({
  className,
  children,
  ...props
}: PromptInputToolsProps) {
  return (
    <div
      className={cn("flex items-center gap-1 [&_button:first-child]:rounded-bl-xl", className)}
      {...props}
    >
      {children}
    </div>
  )
}

// PromptInputButton
interface PromptInputButtonProps extends ComponentProps<typeof Button> {
  children: React.ReactNode
}

export function PromptInputButton({
  className,
  variant = "ghost",
  children,
  ...props
}: PromptInputButtonProps) {
  return (
    <Button
      variant={variant}
      className={cn(
        "shrink-0 gap-1.5 rounded-lg",
        variant === "ghost" && "text-muted-foreground",
        className
      )}
      {...props}
    >
      {children}
    </Button>
  )
}

// PromptInputSubmit
export type SubmitStatus = "ready" | "submitted" | "streaming" | "error"

interface PromptInputSubmitProps extends ComponentProps<typeof Button> {
  status?: SubmitStatus
}

export function PromptInputSubmit({
  status = "ready",
  className,
  ...props
}: PromptInputSubmitProps) {
  const getIcon = () => {
    switch (status) {
      case "submitted":
        return <Loader size={16} />
      case "streaming":
        return <Square className="size-4" />
      case "error":
        return <X className="size-4" />
      case "ready":
      default:
        return <Send className="size-4" />
    }
  }

  return (
    <Button
      type="submit"
      className={className}
      {...props}
    >
      {getIcon()}
    </Button>
  )
}
