'use client'

import { useState, useCallback } from 'react'
import type { QuizQuestion } from '@/types'
import { CheckCircle2, XCircle, Loader, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface QuizComponentProps {
  quizId: string
  topic: string
  questions: QuizQuestion[]
  onComplete: (quizId: string, answers: Record<string, 'A' | 'B' | 'C' | 'D'>) => void
  isSubmitting?: boolean
}

export function QuizComponent({
  quizId,
  topic,
  questions,
  onComplete,
  isSubmitting = false,
}: QuizComponentProps) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, 'A' | 'B' | 'C' | 'D'>>({})
  const [selectedAnswer, setSelectedAnswer] = useState<'A' | 'B' | 'C' | 'D' | null>(null)
  const [showFeedback, setShowFeedback] = useState(false)
  const [isCorrect, setIsCorrect] = useState(false)
  const [showScore, setShowScore] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)
  const [answeredQuestions, setAnsweredQuestions] = useState<Set<number>>(new Set())

  const currentQuestion = questions[currentQuestionIndex]
  const progress = ((currentQuestionIndex + 1) / questions.length) * 100
  const hasAnswered = answeredQuestions.has(currentQuestionIndex)
  const isLastQuestion = currentQuestionIndex === questions.length - 1

  const handleAnswerSelect = useCallback((answer: 'A' | 'B' | 'C' | 'D') => {
    if (hasAnswered || showFeedback) return

    setSelectedAnswer(answer)
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.id]: answer,
    }))

    // Mark question as answered
    setAnsweredQuestions((prev) => new Set(prev).add(currentQuestionIndex))

    // Show immediate feedback
    const correct = answer === currentQuestion.correct_answer
    setIsCorrect(correct)
    setShowFeedback(true)
  }, [currentQuestion, hasAnswered, showFeedback, currentQuestionIndex])

  const handleSubmit = useCallback(() => {
    setShowScore(true)
    setShowFeedback(false)
    onComplete(quizId, answers)
  }, [quizId, answers, onComplete])

  // Auto-submit when last question is answered (for direct submission without score screen)
  const handleLastQuestionSubmit = useCallback(() => {
    setShowFeedback(false)
    setShowScore(true)
    setIsCompleted(true)
    onComplete(quizId, answers)
  }, [quizId, answers, onComplete])

  const handleNextQuestion = useCallback(() => {
    if (currentQuestionIndex < questions.length - 1) {
      // Move to next question
      setCurrentQuestionIndex((prev) => prev + 1)
      setSelectedAnswer(null)
      setShowFeedback(false)
      setIsCorrect(false)
    } else {
      // Last question: automatically submit results without showing score screen
      handleLastQuestionSubmit()
    }
  }, [currentQuestionIndex, questions.length, handleLastQuestionSubmit])

  // Loading state (show when submitting, regardless of showScore)
  if (isSubmitting) {
    return (
      <div className="rounded-2xl bg-black text-white px-6 py-6 space-y-4">
        <div className="flex items-center justify-center gap-2 text-sm">
          <Loader className="w-4 h-4 animate-spin" />
          <span>Ergebnisse werden gespeichert...</span>
        </div>
      </div>
    )
  }

  // Score screen - show after completion or when showScore is true
  if (showScore || isCompleted) {
    const correctCount = Object.entries(answers).reduce((count, [questionId, answer]) => {
      const question = questions.find((q) => q.id === questionId)
      return question && answer === question.correct_answer ? count + 1 : count
    }, 0)
    const score = (correctCount / questions.length) * 100

    return (
      <div className="rounded-2xl bg-black text-white px-6 py-6 space-y-4">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">Quiz abgeschlossen!</h3>
          <div className="text-4xl font-bold mb-1">{score.toFixed(0)}%</div>
          <p className="text-sm text-white/70">
            {correctCount} von {questions.length} Fragen richtig
          </p>
        </div>
        {!isCompleted && (
          <button
            onClick={handleSubmit}
            className="w-full bg-white text-black rounded-lg px-4 py-2 font-medium hover:bg-gray-100 transition-colors"
            disabled={isSubmitting}
          >
            Ergebnisse absenden
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-black text-white px-6 py-6 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/70">Thema: {topic}</span>
          <span className="text-white/70">
            Frage {currentQuestionIndex + 1} von {questions.length}
          </span>
        </div>
        
        {/* Progress Bar */}
        <div className="w-full bg-white/20 rounded-full h-2">
          <div
            className="bg-white h-2 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Question */}
      <div>
        <h3 className="text-lg font-semibold leading-relaxed">
          {currentQuestion.question}
        </h3>
      </div>

      {/* Answer Options */}
      <div className="space-y-2">
        {(['A', 'B', 'C', 'D'] as const).map((option) => {
          const optionText = currentQuestion.options[option]
          const isSelected = selectedAnswer === option
          const isCorrectOption = option === currentQuestion.correct_answer
          
          // Determine button styles based on state
          let buttonClasses = cn(
            'w-full text-left px-4 py-3 rounded-lg border-2 transition-all',
            'hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/50',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )

          if (showFeedback) {
            if (isCorrectOption) {
              buttonClasses = cn(
                buttonClasses,
                'bg-green-500/20 border-green-500'
              )
            } else if (isSelected && !isCorrectOption) {
              buttonClasses = cn(
                buttonClasses,
                'bg-red-500/20 border-red-500'
              )
            } else {
              buttonClasses = cn(
                buttonClasses,
                'bg-white/5 border-white/20'
              )
            }
          } else if (isSelected) {
            buttonClasses = cn(
              buttonClasses,
              'bg-white/20 border-white/50'
            )
          } else {
            buttonClasses = cn(
              buttonClasses,
              'bg-white/5 border-white/20'
            )
          }

          return (
            <button
              key={option}
              className={buttonClasses}
              onClick={() => handleAnswerSelect(option)}
              disabled={hasAnswered || showFeedback}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-lg w-6">{option}</span>
                  <span className="text-sm">{optionText}</span>
                </div>
                {/* Icons only shown when feedback is visible */}
                {showFeedback && isCorrectOption && (
                  <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                )}
                {showFeedback && isSelected && !isCorrectOption && (
                  <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                )}
              </div>
            </button>
          )
        })}
      </div>

      {/* Feedback */}
      {showFeedback && (
        <>
          <div
            className={cn(
              'mt-4 p-4 rounded-lg',
              isCorrect
                ? 'bg-green-500/20 border border-green-500/50'
                : 'bg-red-500/20 border border-red-500/50'
            )}
          >
            <div className="flex items-start gap-2">
              {isCorrect ? (
                <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1 space-y-1">
                <p
                  className={cn(
                    'text-sm font-medium',
                    isCorrect ? 'text-green-300' : 'text-red-300'
                  )}
                >
                  {isCorrect ? 'Richtig!' : 'Falsch'}
                </p>
                {!isCorrect && (
                  <p className="text-sm text-white/80">
                    Die richtige Antwort ist: <strong>{currentQuestion.correct_answer}</strong>
                  </p>
                )}
                <p className="text-sm text-white/70">{currentQuestion.explanation}</p>
              </div>
            </div>
          </div>
          
          {/* Next Question Button */}
          <button
            onClick={handleNextQuestion}
            className="w-full mt-4 bg-white text-black rounded-lg px-4 py-3 font-medium hover:bg-gray-100 transition-colors flex items-center justify-center gap-2"
          >
            <span>{isLastQuestion ? 'Weiter' : 'Nächste Frage'}</span>
            <ChevronRight className="w-5 h-5" />
          </button>
        </>
      )}
    </div>
  )
}
