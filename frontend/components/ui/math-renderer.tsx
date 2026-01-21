"use client"

import { MathJax } from "better-react-mathjax"
import { cn } from "@/lib/utils"

interface MathRendererProps {
  formula: string
  inline?: boolean
  className?: string
}

/**
 * MathRenderer Component
 * 
 * Renders mathematical expressions using MathJax.
 * Supports both inline and display math modes.
 * 
 * @param formula - The LaTeX formula to render
 * @param inline - Whether to render as inline math (default: true)
 * @param className - Additional CSS classes
 */
export function MathRenderer({ 
  formula, 
  inline = true, 
  className 
}: MathRendererProps) {
  // Wrap formula in appropriate delimiters
  const wrappedFormula = inline 
    ? `\\(${formula}\\)`
    : `\\[${formula}\\]`

  return (
    <MathJax
      inline={inline}
      dynamic={true}
      hideUntilTypeset="first"
      className={cn("math-expression", className)}
    >
      {wrappedFormula}
    </MathJax>
  )
}
