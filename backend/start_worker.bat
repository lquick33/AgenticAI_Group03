@echo off
echo Starting Celery Worker for StudyBuddy...
echo Ensure Redis is running and REDIS_URL is correctly set in your .env file!

REM Navigate to backend folder just in case
cd /d "%~dp0"

IF EXIST "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run celery worker
REM -A app.core.celery_app points to the Celery instance
REM Windows: use solo pool to avoid billiard prefork semaphore issues (WinError 5/6)
celery -A app.core.celery_app worker --loglevel=info --pool=solo --concurrency=1
