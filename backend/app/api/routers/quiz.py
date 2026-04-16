import logging
from fastapi import APIRouter, HTTPException

from app.models.schemas import QuizSubmit, QuizResult, QuizResponse
from app.services.quiz_service import submit_quiz_results, get_quiz, get_quiz_result

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/quiz/submit", response_model=QuizResult, status_code=200)
async def submit_quiz(request: QuizSubmit):
    """
    Submit answers for a quiz and get the score.
    Saves the result in the database.
    """
    try:
        result = submit_quiz_results(
            quiz_id=request.quiz_id,
            user_id=request.user_id,
            answers=request.answers
        )
        return result
    except ValueError as e:
        logger.warning(f"Validation error submitting quiz: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting quiz {request.quiz_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to submit quiz: {str(e)}"
        )


@router.get("/quiz/{quiz_id}", response_model=QuizResponse, status_code=200)
async def get_quiz_endpoint(quiz_id: str):
    """
    Retrieve a quiz by ID.
    Always excludes the correct answers from the response.
    """
    try:
        quiz = get_quiz(quiz_id, include_answers=False)
        return quiz
    except ValueError as e:
        logger.warning(f"Validation error fetching quiz: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching quiz {quiz_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch quiz: {str(e)}"
        )
