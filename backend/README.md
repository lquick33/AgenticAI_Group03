# Backend Setup Guide

This guide will help you set up the Lernkompanien backend for development.

## Prerequisites

- Python 3.11 or higher
- pip package manager
- Google Cloud account (for TTS features - optional)
- Supabase account (for database)

## Quick Start

1. **Clone the repository** (if you haven't already)

2. **Set up Python virtual environment**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   # Copy the example file
   cp ../.env.example ../.env
   
   # Edit .env and fill in your API keys
   # See .env.example for all required variables
   ```

5. **Start the backend server**:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Required Environment Variables

### Essential (Required)

These must be set for the backend to work:

- `GOOGLE_API_KEY` - Google Gemini API key
  - Get from: https://aistudio.google.com/app/apikey
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Supabase service role key
  - Get from: https://app.supabase.com/project/_/settings/api

### Optional

- `OPENAI_API_KEY` - OpenAI API key (for alternative LLM)
- `LANGFUSE_PUBLIC_KEY` - Langfuse public key (for observability)
- `LANGFUSE_SECRET_KEY` - Langfuse secret key
- `LANGFUSE_ENABLED` - Set to `true` to enable Langfuse
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## Text-to-Speech (TTS) Setup

The TTS feature is **optional** but enables audio generation for Chinese language learning flashcards.

### Quick Setup (Shared Credentials)

If you're working with the team and have access to shared credentials:

1. Get the service account JSON file from your teammate (via secure channel)
2. Place it in `backend/credentials/`
3. Update `.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=backend/credentials/your-key-file.json
   ```

### Individual Setup

If you want to set up your own credentials:

1. See detailed instructions in [`credentials/README.md`](credentials/README.md)
2. Create a Google Cloud service account with Text-to-Speech API access
3. Download the JSON key file
4. Place it in `backend/credentials/`
5. Update `.env` with the path

### Test TTS Setup

```bash
cd backend
source venv/bin/activate
python test_tts.py
```

If successful, you'll see:
- ✓ All 5 tests passed
- MP3 audio files generated in `backend/test_outputs/`

## Project Structure

```
backend/
  app/
    agents/          # AI agents (TutorAgent, FlashcardAgent)
    api/            # FastAPI endpoints
    core/           # Configuration and settings
    services/       # Business logic services
    tools/          # LangChain tools for agents
  credentials/      # Google Cloud credentials (gitignored)
  supabase/        # Database migrations
  tests/           # Test files
  requirements.txt # Python dependencies
```

## Development

### Running Tests

```bash
# TTS functionality test
python test_tts.py

# Other tests
python -m pytest tests/
```

### Database Migrations

Migrations are in `supabase/migrations/`. Apply them via:
- Supabase Dashboard SQL Editor, or
- Supabase CLI: `supabase db push`

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Document functions with docstrings

## Troubleshooting

### Backend won't start

- Check that all required environment variables are set
- Verify Python version: `python --version` (should be 3.11+)
- Ensure dependencies are installed: `pip install -r requirements.txt`

### TTS not working

- Verify `GOOGLE_APPLICATION_CREDENTIALS` path in `.env` is correct
- Check that the JSON file exists and is valid
- Ensure Text-to-Speech API is enabled in Google Cloud
- See [`credentials/README.md`](credentials/README.md) for detailed troubleshooting

### Import errors

- Make sure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check that you're in the `backend/` directory when running commands

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Google Cloud TTS Documentation](https://cloud.google.com/text-to-speech/docs)
