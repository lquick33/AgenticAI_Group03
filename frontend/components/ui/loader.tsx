"use client"

import { cn } from "@/lib/utils"
import type { HTMLAttributes } from "react"

interface LoaderProps extends HTMLAttributes<HTMLDivElement> {
  size?: number
}

export function Loader({ size = 16, className, ...props }: LoaderProps) {
  return (
    <div
      className={cn("inline-flex animate-spin items-center justify-center", className)}
      {...props}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
          strokeOpacity="0.25"
        />
        <path
          d="M12 2C13.3132 2 14.6136 2.25866 15.8268 2.7612C17.0401 3.26375 18.1425 4.00035 19.0711 4.92893C19.9997 5.85752 20.7362 6.95991 21.2388 8.17317C21.7413 9.38642 22 10.6868 22 12"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}
