import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium tracking-[0.01em] transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary-foreground",
        secondary:
          "border-[var(--app-border-soft)] bg-[var(--app-surface-subtle)] text-muted-foreground",
        destructive:
          "border-transparent bg-destructive/10 text-destructive dark:bg-destructive/20",
        outline:
          "border-[var(--app-border-strong)] bg-[var(--app-surface)] text-muted-foreground",
        success:
          "border-transparent bg-emerald-500/12 text-emerald-700 dark:bg-emerald-500/18 dark:text-emerald-300",
        warning:
          "border-transparent bg-amber-500/12 text-amber-700 dark:bg-amber-500/18 dark:text-amber-300",
        info:
          "border-transparent bg-sky-500/12 text-sky-700 dark:bg-sky-500/18 dark:text-sky-300",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
