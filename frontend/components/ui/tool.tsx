"use client"

import * as React from "react"
import {
  CheckCircleIcon,
  ChevronDownIcon,
  CircleIcon,
  ClockIcon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Loader } from "@/components/ui/loader"
import { cn } from "@/lib/utils"

export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  result?: string
  state?: "pending" | "running" | "completed" | "error"
}

export interface ToolProps extends React.ComponentProps<typeof Collapsible> {
  toolCall: ToolCall
}

const getStatusBadge = (state: ToolCall["state"], hasResult: boolean) => {
  const actualState = hasResult ? state || "completed" : "running"

  const labels: Record<string, string> = {
    pending: "Pending",
    running: "Warte auf Antwort",
    completed: "Completed",
    error: "Error",
  }

  const icons: Record<string, React.ReactNode> = {
    pending: <CircleIcon className="size-4" />,
    running: <Loader size={16} className="text-blue-600" />,
    completed: <CheckCircleIcon className="size-4 text-green-600" />,
    error: <XCircleIcon className="size-4 text-red-600" />,
  }

  return (
    <Badge className="gap-1.5 rounded-full text-xs" variant="secondary">
      {icons[actualState]}
      {labels[actualState]}
    </Badge>
  )
}

export const Tool = ({ className, toolCall, ...props }: ToolProps) => {
  const [isOpen, setIsOpen] = React.useState(false)
  const [hasTimedOut, setHasTimedOut] = React.useState(false)
  const hasResult = Boolean(toolCall.result)

  React.useEffect(() => {
    if (hasResult) {
      setHasTimedOut(false)
      return
    }

    const timeoutId = setTimeout(() => {
      setHasTimedOut(true)
    }, 60000)

    return () => {
      clearTimeout(timeoutId)
    }
  }, [hasResult])

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn("not-prose mb-2 w-full rounded-md border border-border bg-card", className)}
      {...props}
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-4 p-3 hover:bg-muted/50 transition-colors">
        <div className="flex items-center gap-2">
          <WrenchIcon className="size-4 text-muted-foreground" />
          <span className="font-medium text-sm">{toolCall.name}</span>
          {getStatusBadge(toolCall.state, hasResult)}
        </div>
        <ChevronDownIcon
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:animate-in data-[state=open]:slide-in-from-top-2">
        <div className="space-y-4 overflow-hidden p-4 pt-0">
          <div className="space-y-2">
            <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
              Parameters
            </h4>
            <div className="rounded-md bg-muted/50 p-3">
              <pre className="text-xs overflow-x-auto">
                <code>{JSON.stringify(toolCall.args, null, 2)}</code>
              </pre>
            </div>
          </div>

          {!hasResult && !hasTimedOut && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 rounded-md bg-blue-50 dark:bg-blue-950/20 p-3 border border-blue-200 dark:border-blue-900">
                <Loader size={16} className="text-blue-600" />
                <span className="text-xs text-blue-700 dark:text-blue-300">
                  Warte auf Antwort...
                </span>
              </div>
            </div>
          )}

          {!hasResult && hasTimedOut && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 rounded-md bg-yellow-50 dark:bg-yellow-950/20 p-3 border border-yellow-200 dark:border-yellow-900">
                <ClockIcon className="size-4 text-yellow-600" />
                <span className="text-xs text-yellow-700 dark:text-yellow-300">
                  Timeout erreicht - Warte weiterhin auf Antwort...
                </span>
              </div>
            </div>
          )}

          {toolCall.result && (
            <div className="space-y-2">
              <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
                Result
              </h4>
              <div className="rounded-md bg-green-50 dark:bg-green-950/20 p-3 border border-green-200 dark:border-green-900">
                <pre className="text-xs overflow-x-auto">
                  <code>
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(toolCall.result), null, 2)
                      } catch {
                        return toolCall.result
                      }
                    })()}
                  </code>
                </pre>
              </div>
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
