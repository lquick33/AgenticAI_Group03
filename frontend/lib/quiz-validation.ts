/**
 * Quiz validation utilities
 *
 * Provides type guards and validation functions for quiz data structures.
 */

import type { QuizQuestion, QuizData, QuizToolResponse } from '@/types'

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null
}

function hasNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

/**
 * Type guard to check if a value is a valid QuizQuestion
 */
export function isValidQuizQuestion(value: unknown): value is QuizQuestion {
  if (!isRecord(value)) return false

  const options = value.options
  const hasOptions =
    isRecord(options) &&
    typeof options.A === 'string' &&
    typeof options.B === 'string' &&
    typeof options.C === 'string' &&
    typeof options.D === 'string'

  return (
    hasNonEmptyString(value.id) &&
    hasNonEmptyString(value.question) &&
    hasOptions &&
    ['A', 'B', 'C', 'D'].includes(String(value.correct_answer)) &&
    ['easy', 'medium', 'hard'].includes(String(value.difficulty)) &&
    hasNonEmptyString(value.explanation)
  )
}

/**
 * Type guard to check if a value is a valid QuizData
 */
export function isValidQuizData(value: unknown): value is QuizData {
  if (!isRecord(value)) return false

  return (
    hasNonEmptyString(value.topic) &&
    Array.isArray(value.questions) &&
    value.questions.length >= 3 &&
    value.questions.length <= 8 &&
    value.questions.every((question) => isValidQuizQuestion(question))
  )
}

/**
 * Type guard to check if a value is a valid QuizToolResponse
 */
export function isValidQuizToolResponse(value: unknown): value is QuizToolResponse {
  if (!isRecord(value)) return false

  return (
    hasNonEmptyString(value.quiz_id) &&
    isValidQuizData(value.quiz_data) &&
    hasNonEmptyString(value.topic) &&
    typeof value.question_count === 'number' &&
    value.question_count >= 3 &&
    value.question_count <= 8 &&
    typeof value.start_page === 'number' &&
    value.start_page >= 1 &&
    typeof value.end_page === 'number' &&
    value.end_page >= 1
  )
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

  let parsed: unknown
  try {
    parsed = JSON.parse(jsonString)
  } catch (e) {
    throw new Error(`Failed to parse JSON: ${e instanceof Error ? e.message : 'Unknown error'}`)
  }

  if (!isRecord(parsed)) {
    throw new Error('Invalid quiz tool response structure. Expected an object.')
  }

  if (typeof parsed.error === 'string' && parsed.error.length > 0) {
    throw new Error(`Quiz creation failed: ${parsed.error}`)
  }

  const missingFields: string[] = []
  const invalidFields: string[] = []

  if (!hasNonEmptyString(parsed.quiz_id)) {
    missingFields.push('quiz_id')
  }

  if (!('quiz_data' in parsed)) {
    missingFields.push('quiz_data')
  } else if (!isValidQuizData(parsed.quiz_data)) {
    invalidFields.push('quiz_data')
  }

  if (!hasNonEmptyString(parsed.topic)) {
    missingFields.push('topic')
  }

  if (
    typeof parsed.question_count !== 'number' ||
    parsed.question_count < 3 ||
    parsed.question_count > 8
  ) {
    invalidFields.push('question_count')
  }

  if (typeof parsed.start_page !== 'number' || parsed.start_page < 1) {
    invalidFields.push('start_page')
  }

  if (typeof parsed.end_page !== 'number' || parsed.end_page < 1) {
    invalidFields.push('end_page')
  }

  if (missingFields.length > 0 || invalidFields.length > 0) {
    const errorParts: string[] = []
    if (missingFields.length > 0) {
      errorParts.push(`Missing fields: ${missingFields.join(', ')}`)
    }
    if (invalidFields.length > 0) {
      errorParts.push(`Invalid fields: ${invalidFields.join(', ')}`)
    }
    throw new Error(`Invalid quiz tool response structure. ${errorParts.join('; ')}`)
  }

  return parsed as unknown as QuizToolResponse
}

/**
 * Validate quiz data structure
 *
 * @param quizData - Quiz data to validate
 * @returns true if valid, throws Error if invalid
 * @throws Error if validation fails
 */
export function validateQuizData(quizData: unknown): quizData is QuizData {
  if (!isValidQuizData(quizData)) {
    throw new Error('Invalid quiz data structure')
  }
  return true
}
