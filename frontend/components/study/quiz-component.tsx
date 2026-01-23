'use client'

import { useState, useCallback } from 'react'
import type { QuizQuestion, QuizResult } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'

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
  const [completed, setCompleted] = useState(false)

  const currentQuestion = questions[currentQuestionIndex]
  const progress = ((currentQuestionIndex + 1) / questions.length) * 100

  const handleAnswerSelect = useCallback((answer: 'A' | 'B' | 'C' | 'D') => {
    if (showFeedback || completed) return // Prevent changing answer after feedback

    setSelectedAnswer(answer)
    setAnswers((prev) => ({
      ...prev,
      [currentQuestion.id]: answer,
    }))

    // Show immediate feedback
    const correct = answer === currentQuestion.correct_answer
    setIsCorrect(correct)
    setShowFeedback(true)
  }, [currentQuestion, showFeedback, completed])

  const handleNext = useCallback(() => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1)
      setSelectedAnswer(null)
      setShowFeedback(false)
      setIsCorrect(false)
    } else {
      // All questions answered, submit quiz
      setCompleted(true)
      onComplete(quizId, answers)
    }
  }, [currentQuestionIndex, questions.length, answers, onComplete])

  if (completed && isSubmitting) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Quiz wird übermittelt...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (completed) {
    // Show completion state (will be replaced by result message)
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8">
            <CheckCircle2 className="h-12 w-12 text-green-600 mb-4" />
            <p className="text-lg font-semibold text-gray-900">Quiz abgeschlossen!</p>
            <p className="text-gray-600 mt-2">Die Ergebnisse werden verarbeitet...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="text-xl font-semibold">{topic}</CardTitle>
        <div className="mt-2">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Frage {currentQuestionIndex + 1} von {questions.length}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              {currentQuestion.question}
            </h3>
          </div>

          <div className="space-y-2">
            {(['A', 'B', 'C', 'D'] as const).map((option) => {
              const optionText = currentQuestion.options[option]
              const isSelected = selectedAnswer === option
              const isCorrectOption = option === currentQuestion.correct_answer
              
              let buttonVariant: 'default' | 'secondary' | 'destructive' | 'outline' = 'outline'
              let buttonClassName = 'w-full justify-start text-left'
              
              if (showFeedback) {
                if (isCorrectOption) {
                  buttonVariant = 'default'
                  buttonClassName += ' bg-green-100 border-green-500 text-green-900 hover:bg-green-100'
                } else if (isSelected && !isCorrectOption) {
                  buttonVariant = 'destructive'
                  buttonClassName += ' bg-red-100 border-red-500 text-red-900 hover:bg-red-100'
                } else {
                  buttonVariant = 'secondary'
                  buttonClassName += ' opacity-60'
                }
              } else if (isSelected) {
                buttonVariant = 'default'
              }

              return (
                <Button
                  key={option}
                  variant={buttonVariant}
                  className={buttonClassName}
                  onClick={() => handleAnswerSelect(option)}
                  disabled={showFeedback}
                >
                  <span className="font-semibold mr-2">{option}:</span>
                  <span>{optionText}</span>
                  {showFeedback && isSelected && (
                    <span className="ml-auto">
                      {isCorrect ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600" />
                      )}
                    </span>
                  )}
                  {showFeedback && isCorrectOption && !isSelected && (
                    <span className="ml-auto">
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    </span>
                  )}
                </Button>
              )
            })}
          </div>

          {showFeedback && (
            <div className="mt-4 p-4 rounded-lg bg-gray-50">
              <div className="flex items-start gap-2">
                {isCorrect ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <p className={`font-medium ${isCorrect ? 'text-green-900' : 'text-red-900'}`}>
                    {isCorrect ? 'Richtig!' : 'Falsch'}
                  </p>
                  <p className="text-sm text-gray-700 mt-1">{currentQuestion.explanation}</p>
                </div>
              </div>
            </div>
          )}

          {showFeedback && (
            <div className="flex justify-end mt-4">
              <Button onClick={handleNext} disabled={isSubmitting}>
                {currentQuestionIndex < questions.length - 1 ? 'Nächste Frage' : 'Quiz abschließen'}
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
