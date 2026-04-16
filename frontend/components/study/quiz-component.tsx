'use client'

import { useState, useCallback, useMemo } from 'react'
import type { QuizQuestion } from '@/types'
import { CheckCircle2, XCircle, Loader, ChevronRight, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { validateQuizData } from '@/lib/quiz-validation'

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

  const validationError = useMemo(() => {
    try {
      validateQuizData({
        topic,
        questions,
        metadata: {},
      })
      return null
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid quiz data'
      console.error('[QuizComponent] Validation error:', message, error)
      return message
    }
  }, [topic, questions])

  const currentQuestion = questions[currentQuestionIndex] ?? null
  const progress = questions.length > 0 ? ((currentQuestionIndex + 1) / questions.length) * 100 : 0
  const hasAnswered = answeredQuestions.has(currentQuestionIndex)
  const isLastQuestion = questions.length > 0 && currentQuestionIndex === questions.length - 1

  const handleAnswerSelect = useCallback(
    (answer: 'A' | 'B' | 'C' | 'D') => {
      if (!currentQuestion || hasAnswered || showFeedback) return

      setSelectedAnswer(answer)
      setAnswers((prev) => ({
        ...prev,
        [currentQuestion.id]: answer,
      }))
      setAnsweredQuestions((prev) => new Set(prev).add(currentQuestionIndex))

      const correct = answer === currentQuestion.correct_answer
      setIsCorrect(correct)
      setShowFeedback(true)
    },
    [currentQuestion, currentQuestionIndex, hasAnswered, showFeedback]
  )

  const handleSubmit = useCallback(() => {
    setShowScore(true)
    setShowFeedback(false)
    onComplete(quizId, answers)
  }, [answers, onComplete, quizId])

  const handleLastQuestionSubmit = useCallback(() => {
    setShowFeedback(false)
    setShowScore(true)
    setIsCompleted(true)
    onComplete(quizId, answers)
  }, [answers, onComplete, quizId])

  const handleNextQuestion = useCallback(() => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1)
      setSelectedAnswer(null)
      setShowFeedback(false)
      setIsCorrect(false)
      return
    }

    handleLastQuestionSubmit()
  }, [currentQuestionIndex, handleLastQuestionSubmit, questions.length])

  if (validationError) {
    return (
      <div className="rounded-2xl bg-red-50 border border-red-200 text-red-900 px-6 py-6 space-y-4">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
          <div>
            <h3 className="text-lg font-semibold mb-1">Quiz-Daten ungültig</h3>
            <p className="text-sm text-red-700">{validationError}</p>
          </div>
        </div>
      </div>
    )
  }

  if (questions.length === 0) {
    return (
      <div className="rounded-2xl bg-yellow-50 border border-yellow-200 text-yellow-900 px-6 py-6 space-y-4">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          <div>
            <h3 className="text-lg font-semibold mb-1">Keine Fragen verfügbar</h3>
            <p className="text-sm text-yellow-700">Das Quiz enthält keine Fragen.</p>
          </div>
        </div>
      </div>
    )
  }

  if (!currentQuestion) {
    return (
      <div className="rounded-2xl bg-yellow-50 border border-yellow-200 text-yellow-900 px-6 py-6 space-y-4">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          <div>
            <h3 className="text-lg font-semibold mb-1">Frage nicht gefunden</h3>
            <p className="text-sm text-yellow-700">Die aktuelle Frage konnte nicht geladen werden.</p>
          </div>
        </div>
      </div>
    )
  }

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

  if (showScore || isCompleted) {
    const correctCount = Object.entries(answers).reduce((count, [questionId, answer]) => {
      const question = questions.find((candidate) => candidate.id === questionId)
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
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/70">Thema: {topic}</span>
          <span className="text-white/70">
            Frage {currentQuestionIndex + 1} von {questions.length}
          </span>
        </div>

        <div className="w-full bg-white/20 rounded-full h-2">
          <div
            className="bg-white h-2 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold leading-relaxed">{currentQuestion.question}</h3>
      </div>

      <div className="space-y-2">
        {(['A', 'B', 'C', 'D'] as const).map((option) => {
          const optionText = currentQuestion.options[option]
          const isSelected = selectedAnswer === option
          const isCorrectOption = option === currentQuestion.correct_answer

          let buttonClasses = cn(
            'w-full text-left px-4 py-3 rounded-lg border-2 transition-all',
            'hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/50',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )

          if (showFeedback) {
            if (isCorrectOption) {
              buttonClasses = cn(buttonClasses, 'bg-green-500/20 border-green-500')
            } else if (isSelected && !isCorrectOption) {
              buttonClasses = cn(buttonClasses, 'bg-red-500/20 border-red-500')
            } else {
              buttonClasses = cn(buttonClasses, 'bg-white/5 border-white/20')
            }
          } else if (isSelected) {
            buttonClasses = cn(buttonClasses, 'bg-white/20 border-white/50')
          } else {
            buttonClasses = cn(buttonClasses, 'bg-white/5 border-white/20')
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
