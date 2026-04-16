from fastapi import APIRouter

from .chat import router as chat_router
from .quickchat import router as quickchat_router
from .flashcards import router as flashcards_router
from .quiz import router as quiz_router
from .courses import router as courses_router
from .materials import router as materials_router
from .study import router as study_router

api_router = APIRouter()

api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(quickchat_router, tags=["quickchat"])
api_router.include_router(flashcards_router, tags=["flashcards"])
api_router.include_router(quiz_router, tags=["quiz"])
api_router.include_router(courses_router, tags=["courses"])
api_router.include_router(materials_router, tags=["materials"])
api_router.include_router(study_router, tags=["study"])
