/**
 * Quiz validation utilities
 * 
 * Provides type guards and validation functions for quiz data structures.
 */

import type { QuizQuestion, QuizData, QuizToolResponse } from '@/types'

/**
 * Type guard to check if a value is a valid QuizQuestion
 */
export function isValidQuizQuestion(value: any): value is QuizQuestion {
  if (!value || typeof value !== 'object') return false
  
  const hasId = typeof value.id === 'string' && value.id.length > 0
  const hasQuestion = typeof value.question === 'string' && value.question.length > 0
  const hasOptions = 
    value.options && 
    typeof value.options === 'object' &&
    typeof value.options.A === 'string' &&
    typeof value.options.B === 'string' &&
    typeof value.options.C === 'string' &&
    typeof value.options.D === 'string'
  const hasCorrectAnswer = ['A', 'B', 'C', 'D'].includes(value.correct_answer)
  const hasDifficulty = ['easy', 'medium', 'hard'].includes(value.difficulty)
  const hasExplanation = typeof value.explanation === 'string' && value.explanation.length > 0
  
  return hasId && hasQuestion && hasOptions && hasCorrectAnswer && hasDifficulty && hasExplanation
}

/**
 * Type guard to check if a value is a valid QuizData
 */
export function isValidQuizData(value: any): value is QuizData {
  if (!value || typeof value !== 'object') return false
  
  const hasTopic = typeof value.topic === 'string' && value.topic.length > 0
  const hasQuestions = 
    Array.isArray(value.questions) &&
    value.questions.length >= 3 &&
    value.questions.length <= 8 &&
    value.questions.every((q: any) => isValidQuizQuestion(q))
  
  return hasTopic && hasQuestions
}

/**
 * Type guard to check if a value is a valid QuizToolResponse
 */
export function isValidQuizToolResponse(value: any): value is QuizToolResponse {
  if (!value || typeof value !== 'object') return false
  
  const hasQuizId = typeof value.quiz_id === 'string' && value.quiz_id.length > 0
  const hasQuizData = isValidQuizData(value.quiz_data)
  const hasTopic = typeof value.topic === 'string' && value.topic.length > 0
  const hasQuestionCount = 
    typeof value.question_count === 'number' &&
    value.question_count >= 3 &&
    value.question_count <= 8
  const hasStartPage = typeof value.start_page === 'number' && value.start_page >= 1
  const hasEndPage = typeof value.end_page === 'number' && value.end_page >= 1
  
  return hasQuizId && hasQuizData && hasTopic && hasQuestionCount && hasStartPage && hasEndPage
}

/**
 * Parse and validate a quiz tool response from JSON string
 * 
 * @param jsonString - JSON string to parse
 * @returns Parsed and validated QuizToolResponse
 * @throws Error if parsing or validation fails
 */
export function parseQuizToolResponse(jsonString: string): QuizToolResponse {
  if (!jsonString || typeof jsonString !== 'string') {
    throw new Error('Invalid input: expected non-empty string')
  }
  
  let parsed: any
  try {
    parsed = JSON.parse(jsonString)
  } catch (e) {
    throw new Error(`Failed to parse JSON: ${e instanceof Error ? e.message : 'Unknown error'}`)
  }
  
  // Check for error response
  if (parsed.error) {
    throw new Error(`Quiz creation failed: ${parsed.error}`)
  }
  
  // Validate structure
  if (!isValidQuizToolResponse(parsed)) {
    const missingFields: string[] = []
    if (!parsed.quiz_id) missingFields.push('quiz_id')
    if (!parsed.quiz_data) missingFields.push('quiz_data')
    if (!parsed.topic) missingFields.push('topic')
    if (!parsed.question_count) missingFields.push('question_count')
    if (!parsed.start_page) missingFields.push('start_page')
    if (!parsed.end_page) missingFields.push('end_page')
    
    throw new Error(
      `Invalid quiz tool response structure. Missing or invalid fields: ${missingFields.join(', ')}`
    )
  }
  
  return parsed
}

/**
 * Validate quiz data structure
 * 
 * @param quizData - Quiz data to validate
 * @returns true if valid, throws Error if invalid
 * @throws Error if validation fails
 */
export function validateQuizData(quizData: any): quizData is QuizData {
  if (!isValidQuizData(quizData)) {
    throw new Error('Invalid quiz data structure')
  }
  return true
}
