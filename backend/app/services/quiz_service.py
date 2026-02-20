"""
Quiz Service

Business logic for quiz creation, retrieval, submission, and scoring.
"""

import json
import logging
from typing import Optional, Dict, List
from datetime import datetime

from app.adapters.supabase.client import get_supabase_client
from app.models.schemas import QuizData, QuizResult, QuestionResult

logger = logging.getLogger(__name__)


def save_quiz(
    quiz_data: QuizData,
    course_material_id: str,
    user_id: str,
    start_page: int,
    end_page: int,
    topic_name: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> str:
    """
    Save quiz data to database.
    
    Args:
        quiz_data: QuizData Pydantic model with questions and metadata
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID)
        start_page: Starting page number (1-indexed)
        end_page: Ending page number (1-indexed)
        topic_name: Optional topic name (defaults to quiz_data.topic)
        conversation_id: Optional conversation ID where quiz was created
        
    Returns:
        Quiz ID (UUID)
        
    Raises:
        Exception: If save operation fails
    """
    client = get_supabase_client()
    
    try:
        topic = topic_name or quiz_data.topic
        
        # Convert QuizData to dict for JSONB storage
        quiz_dict = quiz_data.model_dump()
        
        # Insert quiz record
        response = client.table("quizzes").insert({
            "course_material_id": course_material_id,
            "user_id": user_id,
            "topic_name": topic,
            "start_page": start_page,
            "end_page": end_page,
            "quiz_data": quiz_dict,
            "conversation_id": conversation_id
        }).execute()
        
        if response.data and len(response.data) > 0:
            quiz_id = response.data[0]["id"]
            logger.info(
                f"Quiz saved: {quiz_id} "
                f"(material: {course_material_id}, pages: {start_page}-{end_page}, "
                f"questions: {len(quiz_data.questions)})"
            )
            return quiz_id
        else:
            raise Exception("Failed to save quiz: no data returned")
    
    except Exception as e:
        logger.error(f"Failed to save quiz: {str(e)}", exc_info=True)
        raise Exception(f"Failed to save quiz: {str(e)}")


def get_quiz(quiz_id: str, user_id: str) -> Optional[Dict]:
    """
    Get quiz data from database.
    
    Args:
        quiz_id: Quiz ID (UUID)
        user_id: User ID for authorization (RLS)
        
    Returns:
        Quiz record as dict, or None if not found
        
    Raises:
        Exception: If query fails
    """
    client = get_supabase_client()
    
    try:
        response = client.table("quizzes").select(
            "id, course_material_id, user_id, topic_name, start_page, end_page, quiz_data, created_at, conversation_id"
        ).eq("id", quiz_id).eq("user_id", user_id).single().execute()
        
        if response.data:
            return response.data
        else:
            return None
    
    except Exception as e:
        logger.error(f"Failed to get quiz {quiz_id}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to get quiz: {str(e)}")


def calculate_score(quiz_data: QuizData, answers: Dict[str, str]) -> tuple[float, int, int, List[QuestionResult]]:
    """
    Calculate quiz score and generate detailed question results.
    
    Args:
        quiz_data: QuizData with questions
        answers: User answers as dict mapping question_id to answer (A, B, C, or D)
        
    Returns:
        Tuple of (score, correct_count, total_questions, question_results)
        - score: Float from 0.0 to 1.0
        - correct_count: Number of correct answers
        - total_questions: Total number of questions
        - question_results: List of QuestionResult objects
    """
    questions = quiz_data.questions
    total_questions = len(questions)
    correct_count = 0
    question_results = []
    
    for question in questions:
        question_id = question.id
        user_answer = answers.get(question_id, "")
        correct_answer = question.correct_answer
        is_correct = user_answer == correct_answer
        
        if is_correct:
            correct_count += 1
        
        question_results.append(
            QuestionResult(
                question_id=question_id,
                user_answer=user_answer if user_answer else "N/A",
                correct_answer=correct_answer,
                correct=is_correct,
                explanation=question.explanation
            )
        )
    
    score = correct_count / total_questions if total_questions > 0 else 0.0
    
    return score, correct_count, total_questions, question_results


def submit_quiz_results(quiz_id: str, user_id: str, answers: Dict[str, str]) -> QuizResult:
    """
    Submit quiz answers and save results to database.
    
    Args:
        quiz_id: Quiz ID (UUID)
        user_id: User ID (UUID)
        answers: User answers as dict mapping question_id to answer (A, B, C, or D)
        
    Returns:
        QuizResult with score, question results, and completion timestamp
        
    Raises:
        ValueError: If quiz not found, already submitted, or validation fails
        Exception: If submission fails
    """
    client = get_supabase_client()
    
    try:
        # Get quiz data
        quiz_record = get_quiz(quiz_id, user_id)
        if not quiz_record:
            raise ValueError(f"Quiz not found: {quiz_id}")
        
        # Check if already submitted
        existing_result = get_quiz_result(quiz_id, user_id)
        if existing_result:
            raise ValueError("Quiz already submitted. Only one attempt allowed per quiz.")
        
        # Parse quiz data
        quiz_data_dict = quiz_record["quiz_data"]
        quiz_data = QuizData(**quiz_data_dict)
        
        # Calculate score
        score, correct_count, total_questions, question_results = calculate_score(quiz_data, answers)
        
        # Convert question results to dict for JSONB storage
        question_results_dict = [qr.model_dump() for qr in question_results]
        
        # Insert quiz result
        response = client.table("quiz_results").insert({
            "quiz_id": quiz_id,
            "user_id": user_id,
            "answers": answers,
            "score": score,
            "correct_count": correct_count,
            "total_questions": total_questions,
            "question_results": question_results_dict
        }).execute()
        
        if response.data and len(response.data) > 0:
            result_id = response.data[0]["id"]
            completed_at = response.data[0]["completed_at"]
            
            logger.info(
                f"Quiz results saved: {result_id} "
                f"(quiz: {quiz_id}, score: {score:.2%}, {correct_count}/{total_questions})"
            )
            
            return QuizResult(
                quiz_id=quiz_id,
                score=score,
                correct_count=correct_count,
                total_questions=total_questions,
                question_results=question_results,
                completed_at=completed_at,
                tutor_feedback=None  # Will be filled by API endpoint
            )
        else:
            raise Exception("Failed to save quiz results: no data returned")
    
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to submit quiz results: {str(e)}", exc_info=True)
        raise Exception(f"Failed to submit quiz results: {str(e)}")


def get_quiz_result(quiz_id: str, user_id: str) -> Optional[Dict]:
    """
    Get quiz result for a user.
    
    Args:
        quiz_id: Quiz ID (UUID)
        user_id: User ID
        
    Returns:
        Quiz result record as dict, or None if not found
        
    Raises:
        Exception: If query fails
    """
    client = get_supabase_client()
    
    try:
        response = client.table("quiz_results").select(
            "id, quiz_id, user_id, answers, score, correct_count, total_questions, question_results, completed_at"
        ).eq("quiz_id", quiz_id).eq("user_id", user_id).single().execute()
        
        if response.data:
            return response.data
        else:
            return None
    
    except Exception as e:
        logger.error(f"Failed to get quiz result: {str(e)}", exc_info=True)
        return None
