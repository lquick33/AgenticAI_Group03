"use client"

import { useState, useRef } from 'react'
import { Conversation, ConversationContent, ConversationEmptyState } from '@/components/ai/conversation'
import { Message, MessageContent } from '@/components/ai/message'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Send, Loader2 } from 'lucide-react'
import type { ChatMessage } from '@/types'

interface ChatInterfaceProps {
  messages: ChatMessage[]
  onSend: (message: string) => void
  isLoading: boolean
  isStreaming?: boolean
}

export function ChatInterface({
  messages,
  onSend,
  isLoading,
  isStreaming = false,
}: ChatInterfaceProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [inputValue, setInputValue] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inputValue.trim() && !isLoading) {
      onSend(inputValue.trim())
      setInputValue('')
    }
  }

  return (
    <div className="flex flex-col h-full">
      <Conversation className="flex-1 overflow-y-auto">
        <ConversationContent>
          {messages.length === 0 ? (
            <ConversationEmptyState
              title="Noch keine Nachrichten"
              description="Beginne eine Unterhaltung mit dem Tutor"
            />
          ) : (
            messages.map((message) => (
              <Message
                key={message.id}
                from={message.role === 'user' ? 'user' : 'assistant'}
              >
                <MessageContent>
                  {message.content}
                </MessageContent>
              </Message>
            ))
          )}
          {isStreaming && (
            <Message from="assistant">
              <MessageContent>
                <Loader2 className="h-4 w-4 animate-spin" />
              </MessageContent>
            </Message>
          )}
        </ConversationContent>
      </Conversation>

      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Frage stellen..."
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !inputValue.trim()}>
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
