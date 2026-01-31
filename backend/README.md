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

## Anki Integration (Docker)

The Anki integration enables the agent to track user knowledge levels and sync flashcards to the user's Anki account via AnkiConnect.

### Prerequisites

- Docker and Docker Compose installed
- An AnkiWeb account (free at https://ankiweb.net/)

### Quick Start

1. **Start the Anki Docker container**:
   ```bash
   # From the project root (where docker-compose.yml is located)
   docker compose up -d
   ```

2. **First-time AnkiWeb login** (required once):
   - Connect to the VNC server: `open vnc://localhost:5900`
   - Or use a VNC client (RealVNC Viewer recommended) to connect to `localhost:5900`
   - In the Anki window, go to **Tools > Preferences > Syncing**
   - Click **Login to AnkiWeb** and enter your credentials
   - Click **Sync** to complete the initial sync

3. **Verify the connection**:
   ```bash
   curl http://localhost:8765 -X POST -d '{"action": "version", "version": 6}'
   # Should return: {"result": 6, "error": null}
   ```

### Docker Services

The `docker-compose.yml` includes:

| Service | Port | Description |
|---------|------|-------------|
| `anki` | 8765 | AnkiConnect API (for flashcard operations) |
| `anki` | 5900 | VNC server (for GUI access and AnkiWeb login) |

### Knowledge Tracking Features

Once Anki is running and synced, the agent can:

- **Track mastery levels** per deck with detailed metrics:
  - Card distribution (new, learning, young, mature)
  - Mastery score (0.0-1.0) based on spaced repetition data
  - Retention rate, average ease factor, intervals
  
- **Course-aware flashcard creation**:
  - Auto-generates deck names: "Course Title::Lecture Name"
  - Links cards to course materials in the database
  
- **Study recommendations** based on:
  - Low-mastery decks needing attention
  - New cards waiting to be studied
  - Retention rate issues

### Agent Tools

The following tools are available to agents:

| Tool | Description |
|------|-------------|
| `get_knowledge_levels()` | Get mastery for all Anki decks |
| `get_course_knowledge_levels()` | Per-lecture breakdown for a course |
| `create_course_flashcard()` | Create card with auto deck naming |
| `create_course_flashcards_batch()` | Bulk card creation |

### Troubleshooting

**Container won't start**:
- Check Docker is running: `docker ps`
- Check logs: `docker compose logs anki`

**AnkiConnect not responding**:
- Ensure container is running: `docker compose ps`
- Check port isn't in use: `lsof -i :8765`

**VNC connection issues**:
- Use a proper VNC client (macOS Screen Sharing may have issues)
- Try RealVNC Viewer or TigerVNC
- VNC has no password by default

**Sync fails**:
- Ensure you're logged into AnkiWeb via VNC
- Check internet connectivity in the container
- Try manual sync via VNC: Tools > Sync

## Project Structure

```
backend/
  app/
    agents/          # AI agents (TutorAgent, FlashcardAgent, QuizAgent)
    api/            # FastAPI endpoints
    core/           # Configuration and settings
    services/       # Business logic services
      anki/         # Anki integration (AnkiClient, KnowledgeService)
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
