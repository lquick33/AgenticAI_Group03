#!/bin/bash
echo "Starting Celery Worker for StudyBuddy..."
echo "Ensure Redis is running and REDIS_URL is correctly set in your .env file!"

# Go to the script directory
cd "$(dirname "$0")"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Start the Celery worker
celery -A app.core.celery_app worker --loglevel=info
