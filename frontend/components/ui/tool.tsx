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
import { cn } from "@/lib/utils"

export interface ToolCall {
  id: string
  name: string
  args: Record<string, any>
  state?: "pending" | "running" | "completed" | "error"
}

export interface ToolProps extends React.ComponentProps<typeof Collapsible> {
  toolCall: ToolCall
}

const getStatusBadge = (state: ToolCall["state"] = "completed") => {
  const labels: Record<string, string> = {
    pending: "Pending",
    running: "Running",
    completed: "Completed",
    error: "Error",
  }

  const icons: Record<string, React.ReactNode> = {
    pending: <CircleIcon className="size-4" />,
    running: <ClockIcon className="size-4 animate-pulse" />,
    completed: <CheckCircleIcon className="size-4 text-green-600" />,
    error: <XCircleIcon className="size-4 text-red-600" />,
  }

  return (
    <Badge className="gap-1.5 rounded-full text-xs" variant="secondary">
      {icons[state]}
      {labels[state]}
    </Badge>
  )
}

export const Tool = ({ className, toolCall, ...props }: ToolProps) => {
  const [isOpen, setIsOpen] = React.useState(false)

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
          {getStatusBadge(toolCall.state)}
        </div>
        <ChevronDownIcon
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2 data-[state=open]:animate-in data-[state=open]:slide-in-from-top-2">
        <div className="space-y-2 overflow-hidden p-4 pt-0">
          <h4 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
            Parameters
          </h4>
          <div className="rounded-md bg-muted/50 p-3">
            <pre className="text-xs overflow-x-auto">
              <code>{JSON.stringify(toolCall.args, null, 2)}</code>
            </pre>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
