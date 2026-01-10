# File Documentation

This file documents the purpose and key components of files added to the Lernkompanien project.

## Database Schema Files

### `supabase/migrations/20260110111927_initial_schema.sql`

**Purpose**: Initial database migration file that sets up the complete Supabase database schema for the Lernkompanien learning platform.

**Key Components**:
- **ENUM Types**: Defines 6 custom enum types (learning_style_enum, agent_persona_enum, unit_status_enum, file_status_enum, sender_role_enum, session_type_enum)
- **Tables**: Creates 9 core tables:
  - `profiles`: Extends Supabase auth.users with additional user information
  - `user_preferences`: Stores onboarding quiz results and user settings
  - `courses`: User's courses/subjects
  - `course_materials`: Uploaded PDF/PPTX files with processing status
  - `page_analyses`: **Core table** - stores structured JSON analysis from GPT-4o Vision (multimodal approach)
  - `learning_units`: Calendar events/study sessions with Google Calendar sync support
  - `flashcards`: Generated flashcards with spaced repetition fields
  - `conversations`: Chat sessions with session_type and metadata
  - `messages`: Individual chat messages with context linking to page_analyses
- **RLS Policies**: Row Level Security policies ensuring users can only access their own data
- **Triggers**: Automatic `updated_at` timestamp updates for relevant tables
- **Indexes**: Performance indexes for common query patterns
- **Storage**: Bucket creation and policies for course materials storage

**Dependencies**: Requires Supabase PostgreSQL database with uuid-ossp extension

**Usage**: Execute via Supabase Dashboard SQL Editor or Supabase CLI (`supabase db push`)

---

### `supabase/migrations/README.md`

**Purpose**: Documentation file explaining the migration structure, execution methods, and schema overview.

**Key Components**:
- Migration execution instructions (Dashboard vs CLI)
- Verification checklist
- Schema relationship diagram
- Notes on key design decisions

**Dependencies**: None (standalone documentation)

---

## Backend Configuration Files

### `backend/requirements.txt`

**Purpose**: Python dependency management file that lists all required packages for the FastAPI backend application.

**Key Components**:
- **FastAPI Framework**: `fastapi`, `uvicorn` - Web framework and ASGI server
- **AI Orchestration**: `langgraph`, `langchain`, `langserve` - Agent state machines and LLM integration
- **LLM Providers**: `openai`, `google-generativeai` - Support for OpenAI GPT-4o and Google Gemini
- **PDF Processing**: `pdf2image`, `pillow` - Convert PDF pages to images for multimodal analysis
- **Database**: `supabase`, `psycopg2-binary` - Supabase client and PostgreSQL adapter
- **Data Validation**: `pydantic`, `pydantic-settings` - Request/response validation and settings management
- **Utilities**: `python-dotenv`, `httpx`, `aiohttp` - Environment variables and async HTTP clients

**Dependencies**: Requires Python 3.11+ and pip package manager

**Usage**: 
```bash
# After activating virtual environment:
pip install -r requirements.txt
```

**Note**: Optional packages (Celery, Redis, testing tools) are commented out and can be uncommented as needed

---

### `backend/poc_vision_gemini.py`

**Purpose**: Proof of Concept script demonstrating vision-first slide analysis using Google Gemini's multimodal capabilities via LangChain with structured Pydantic output.

**Key Components**:
- **SlideAnalysis Pydantic Model**: Defines structured output schema with `summary`, `key_terms`, `exam_questions` (exactly 2), and `diagram_description` fields
- **Image Processing**: `load_image_as_base64()` function that loads local images and converts them to base64 data URI format for LangChain
- **Gemini Model Setup**: `get_gemini_model()` function with automatic model selection (tries `gemini-2.0-flash-exp` first, falls back to `gemini-1.5-flash`)
- **Structured Output**: Uses LangChain's `with_structured_output()` to ensure type-safe Pydantic model responses
- **Analysis Function**: `analyze_slide()` function that processes slide images and returns structured analysis results
- **LangGraph Compatibility**: Code structure designed for future extraction into LangGraph node functions

**Key Functions**:
- `load_image_as_base64(image_path: str) -> str`: Loads and encodes images as base64 data URIs
- `get_gemini_model(api_key: str) -> ChatGoogleGenerativeAI`: Initializes Gemini model with fallback logic
- `analyze_slide(image_path: str, api_key: Optional[str] = None) -> SlideAnalysis`: Main analysis function that processes slides

**Dependencies**: 
- `langchain-google-genai` - Google Gemini integration
- `pydantic` - Structured output validation
- `python-dotenv` - Environment variable loading
- `pillow` - Image processing

**Usage**:
```bash
# With default test_slide.jpg in backend/ directory:
python backend/poc_vision_gemini.py

# With custom image path:
python backend/poc_vision_gemini.py path/to/slide.jpg
```

**Environment Variables**:
- `GOOGLE_API_KEY` - Required Google API key for Gemini access (must be set in `.env` file)

**Future Integration**:
This PoC script will be refactored into:
- Service: `backend/app/services/multimodal_analyzer.py` - Production service for slide analysis
- LangGraph Node: Extracted `analyze_slide()` function will become an async node function that accepts state and returns updated state with analysis results
- Database Integration: Results will be stored in `page_analyses` table in Supabase

**Related Files**:
- `PROJECT_PLAN.md` - Documents the vision-first multimodal analysis approach
- `AGENT_DEVELOPMENT_RULES.md` - Guidelines for LangGraph node function patterns

---

## Frontend Configuration Files

### `frontend/package.json`

**Purpose**: Node.js dependency management file that lists all required packages for the Next.js frontend application.

**Key Components**:
- **Next.js Framework**: `next@16.1.1` - React framework with App Router
- **React**: `react@19.2.3`, `react-dom@19.2.3` - UI library
- **TypeScript**: `typescript@^5` - Type safety
- **Styling**: `tailwindcss@^4` - Utility-first CSS framework
- **PDF Rendering**: `react-pdf@^10.3.0` - Display PDFs in browser
- **Calendar**: `react-big-calendar@^1.19.4` - Calendar visualization
- **Panels**: `react-resizable-panels@^4.3.3` - Split-screen resizable panels
- **Database**: `@supabase/supabase-js@^2.90.1` - Supabase client
- **Forms**: `react-hook-form@^7.70.0`, `@hookform/resolvers@^5.2.2`, `zod@^4.3.5` - Form handling and validation
- **Utilities**: `date-fns@^4.1.0` - Date manipulation
- **UI Components**: `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react` - shadcn/ui dependencies

**Dependencies**: Requires Node.js 18+ and npm package manager

**Usage**: 
```bash
npm install
npm run dev  # Start development server
```

---

### `frontend/components.json`

**Purpose**: Configuration file for shadcn/ui component library setup.

**Key Components**:
- **Style**: Default shadcn/ui style configuration
- **RSC**: React Server Components enabled
- **Tailwind**: CSS variables and theme configuration
- **Aliases**: Path aliases for components, utils, hooks, etc.

**Dependencies**: Requires Next.js and Tailwind CSS to be configured

**Usage**: Used automatically by `npx shadcn@latest add [component]` command

---

### `frontend/tsconfig.json`

**Purpose**: TypeScript configuration file with strict mode enabled.

**Key Components**:
- **Strict Mode**: Enabled for type safety
- **App Router**: Configured for Next.js App Router
- **Path Aliases**: `@/*` maps to project root
- **Target**: ES2017 for modern JavaScript features

**Dependencies**: Requires TypeScript 5+

---

### `frontend/lib/supabase.ts`

**Purpose**: Supabase client initialization and configuration.

**Key Components**:
- Creates Supabase client instance
- Reads environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Exports configured client for use throughout the application

**Dependencies**: Requires `@supabase/supabase-js` package

**Usage**: Import and use in components: `import { supabase } from '@/lib/supabase'`

---

### `frontend/lib/utils.ts`

**Purpose**: Utility functions for className merging (used by shadcn/ui components).

**Key Components**:
- `cn()` function: Merges Tailwind CSS classes with conflict resolution
- Uses `clsx` and `tailwind-merge` for intelligent class merging

**Dependencies**: Requires `clsx` and `tailwind-merge` packages

**Usage**: Used by all shadcn/ui components for className handling

---

### `frontend/types/index.ts`

**Purpose**: TypeScript type definitions matching the Supabase database schema.

**Key Components**:
- **Profile**: User profile type
- **UserPreferences**: Learning style and agent persona preferences
- **Course**: Course/subject type
- **CourseMaterial**: Uploaded material files (PDF, PPTX, etc.)
- **PageAnalysis**: Structured JSON analysis from multimodal LLM
- **LearningUnit**: Calendar events and study sessions
- **Conversation**: Chat session metadata
- **Message**: Individual chat messages
- **Flashcard**: Generated flashcards

**Dependencies**: Types match Supabase schema from `supabase/migrations/20260110111927_initial_schema.sql`

**Usage**: Import types in components: `import type { Course } from '@/types'`

---

### Frontend Directory Structure

**Purpose**: Organized folder structure following Next.js App Router conventions and project requirements.

**Structure**:
```
frontend/
├── app/                    # Next.js App Router pages
│   ├── (auth)/            # Auth route group
│   │   ├── login/
│   │   └── register/
│   └── (dashboard)/       # Protected route group
│       ├── dashboard/
│       ├── courses/
│       │   └── [id]/
│       │       └── study/
│       ├── calendar/
│       └── settings/
├── components/
│   ├── ui/                # shadcn/ui components
│   └── features/          # Feature-specific components
├── lib/                   # Utilities and helpers
├── types/                 # TypeScript type definitions
└── hooks/                 # Custom React hooks
```

**Dependencies**: Follows Next.js 14/15 App Router conventions (NOT Pages Router)

---

## Documentation Files

### `AGENT_DEVELOPMENT_RULES.md`

**Purpose**: Comprehensive rulebook and guidelines document for developing AI agents in the Lernkompanien project, based on the Agentic AI course requirements from `old_repo`.

**Key Components**:
- **Architecture Overview**: BaseAgent pattern, State schema definition, Graph building patterns
- **Agent Development**: Step-by-step guide for creating new agents, graph structure definition, node function implementation, conditional edges and routing
- **State Management**: MessagesState usage, custom state fields, state reducers
- **Tool Development**: BaseTool pattern, LangChain tool conversion, async tool support, tool registry pattern
- **Memory & Persistence**: Checkpointing setup, thread management, long-term memory (Store), conversation history
- **Async & Streaming**: Async node functions, streaming responses, error handling in async context
- **Best Practices**: System message handling, error handling, logging & debugging, testing patterns
- **Code Examples**: Complete examples for SimpleAgent, ToolAgent, AsyncToolAgent, and DynamicPromptAgent patterns

**Key Rules Documented**:
- ✅ MUSS-Regeln (Mandatory): All agents must inherit from BaseAgent, State must extend MessagesState, Type hints required, etc.
- 💡 SOLLTE-Regeln (Best Practices): Use async for I/O, streaming for long responses, error handling, etc.
- ❌ NICHT-Regeln (Anti-Patterns): Don't use plain dict for state, don't throw exceptions in nodes, etc.

**Dependencies**: Based on patterns from `old_repo/agentic_ai/agents/` and `old_repo/agentic_ai/tools/`

**Usage**: 
- Reference for all team members when developing agents
- Integrated into `.cursorrules` for Cursor AI assistance
- Should be consulted before creating new agents or tools

**Related Files**: 
- `.cursorrules` - References this document in Agent Development Guidelines section
- `old_repo/agentic_ai/` - Source of patterns and examples

---

## Backend Application Files

### `backend/app/main.py`

**Purpose**: FastAPI application entry point and initialization.

**Key Components**:
- FastAPI app instance with metadata (title, version, description)
- CORS middleware configuration for Next.js frontend
- API router mounting at `/api` prefix
- Health check endpoint at `/health`
- Root endpoint with welcome message
- Global exception handlers for error responses
- Uvicorn server configuration for development

**Dependencies**: 
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `app.core.config` - Application settings
- `app.api.endpoints` - API route handlers

**Usage**: 
```bash
# Development
python -m app.main

# Or with uvicorn
uvicorn app.main:app --reload
```

---

### `backend/app/core/config.py`

**Purpose**: Centralized configuration management using Pydantic Settings.

**Key Components**:
- `Settings` class extending `BaseSettings` from `pydantic-settings`
- Environment variable loading from `.env` file
- Required settings: `GOOGLE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- Optional settings: `OPENAI_API_KEY`, `APP_NAME`, `APP_VERSION`, `DEBUG`
- Singleton pattern with exported `settings` instance

**Environment Variables**:
- `GOOGLE_API_KEY` - Google Gemini API key (required)
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `SUPABASE_URL` - Supabase project URL (required)
- `SUPABASE_KEY` - Supabase service role key (required)

**Dependencies**: Requires `pydantic-settings` package

**Usage**: Import settings throughout the application: `from app.core.config import settings`

---

### `backend/app/models/schemas.py`

**Purpose**: Pydantic models for request/response validation and data structures.

**Key Components**:
- **SlideAnalysis**: Structured analysis result from multimodal LLM (summary, key_terms, exam_questions, diagram_description)
- **PageAnalysisResponse**: Response model for single page analysis
- **UploadResponse**: Response model for PDF upload endpoint
- **ErrorResponse**: Standardized error format

**Key Features**:
- Type-safe data validation
- Field descriptions for API documentation
- Validation constraints (e.g., exam_questions must be exactly 2)

**Dependencies**: Requires `pydantic` package

**Usage**: Import schemas in endpoints and services: `from app.models.schemas import SlideAnalysis, UploadResponse`

---

### `backend/app/services/analyzer.py`

**Purpose**: Multimodal slide analysis service using Google Gemini vision model.

**Key Components**:
- `analyze_pdf_page(image_bytes: bytes) -> SlideAnalysis`: Main analysis function that processes image bytes
- `get_gemini_model(api_key: str) -> ChatGoogleGenerativeAI`: Model initialization with fallback logic
- `image_bytes_to_base64(image_bytes: bytes, format: str) -> str`: Image encoding helper

**Key Features**:
- Accepts image bytes (from pdf2image conversion) instead of file paths
- Model selection: tries `gemini-2.5-flash` first, falls back to `gemini-1.5-flash`
- Structured output using LangChain's `with_structured_output()`
- Error handling with specific exceptions
- Designed for async/await usage

**Dependencies**: 
- `langchain-google-genai` - Gemini integration
- `pillow` - Image processing
- `app.core.config` - Settings
- `app.models.schemas` - SlideAnalysis model

**Usage**: 
```python
from app.services.analyzer import analyze_pdf_page
analysis = analyze_pdf_page(image_bytes)
```

**Related Files**: 
- `backend/poc_vision_gemini.py` - Original PoC implementation (this service extracted from PoC)
- `backend/app/services/pdf_processor.py` - Background processing service that uses this analyzer

**Note**: As of latest update, `analyze_pdf_page` is now async (`async def`) to support parallel processing.

---

### `backend/app/services/pdf_processor.py`

**Purpose**: Asynchronous background processing service for PDF files with parallel page analysis.

**Key Components**:
- `process_pdf_background(material_id, file_bytes, user_id, max_concurrent=5) -> None`: Main background processing function
- `process_single_page(semaphore, material_id, page_number, image, user_id) -> tuple`: Async task for processing a single page
- `pil_image_to_bytes(image, format) -> bytes`: Helper to convert PIL Image to bytes

**Key Features**:
- **Asynchronous Processing**: Runs in background via FastAPI BackgroundTasks
- **Parallel Page Analysis**: Processes up to 5 pages simultaneously (configurable via `max_concurrent`)
- **Rate Limit Protection**: Uses `asyncio.Semaphore` to limit concurrent API requests
- **Status Management**: Updates `course_materials.processing_status` throughout lifecycle:
  - `uploading` → `processing` → `completed` / `error`
- **Error Handling**: Continues processing even if individual pages fail
- **Progress Tracking**: Logs progress and errors for monitoring

**Processing Flow**:
1. Set status to 'processing'
2. Convert PDF bytes to images using `pdf2image`
3. Create async tasks for all pages
4. Process pages in parallel batches (semaphore-limited)
5. For each page:
   - Convert PIL Image to bytes
   - Call `analyze_pdf_page()` (async)
   - Save result to `page_analyses` table
6. Update final status based on results

**Error Handling**:
- Failed page conversions: Log error, continue with other pages
- API failures: Individual page errors logged, processing continues
- All pages failed: Status set to 'error' with error message
- Partial success: Status set to 'completed' with warning about failed pages

**Dependencies**: 
- `asyncio` - Async/await support and semaphore
- `pdf2image` - PDF to image conversion
- `pillow` - Image processing
- `app.services.analyzer` - Page analysis service (async)
- `app.services.storage` - Database operations

**Usage**: Called automatically by FastAPI BackgroundTasks from upload endpoint:
```python
background_tasks.add_task(
    process_pdf_background,
    material_id=material_id,
    file_bytes=file_bytes,
    user_id=user_id,
    max_concurrent=5
)
```

**Related Files**: 
- `backend/app/api/endpoints.py` - Upload endpoint that triggers background processing
- `backend/app/services/analyzer.py` - Async page analysis function

---

### `backend/app/services/storage.py`

**Purpose**: Supabase Storage and Database operations for file uploads and analysis storage.

**Key Components**:
- `get_supabase_client() -> Client`: Singleton Supabase client initialization
- `upload_pdf_to_storage(file_bytes, filename, user_id) -> str`: Upload PDF to Supabase Storage bucket
- `create_course_material(...) -> dict`: Create course_material record in database
- `update_processing_status(material_id, status, error_message) -> None`: Update processing status
- `save_page_analysis(course_material_id, page_number, analysis, user_id) -> dict`: Save analysis to `page_analyses` table

**Key Features**:
- Supabase client singleton pattern
- Storage bucket operations (default: "course-materials")
- Database operations using Supabase query builder (not raw SQL)
- Handles both structured fields and JSONB storage for `raw_analysis`
- Error handling for storage and database failures

**Database Tables Used**:
- `course_materials`: Stores PDF metadata and processing status
- `page_analyses`: Stores structured analysis results per page

**Dependencies**: 
- `supabase` - Supabase Python client
- `app.core.config` - Settings for Supabase credentials
- `app.models.schemas` - SlideAnalysis model

**Usage**: Import functions in endpoints: `from app.services.storage import upload_pdf_to_storage, save_page_analysis`

---

### `backend/app/api/endpoints.py`

**Purpose**: FastAPI route handlers for PDF upload and processing.

**Key Components**:
- `POST /api/upload`: PDF upload endpoint with asynchronous background processing:
  1. Validates user and course
  2. Accepts PDF file via `UploadFile`
  3. Uploads PDF to Supabase Storage
  4. Creates `course_material` record with status 'uploading'
  5. Starts background task for parallel page processing
  6. Returns immediately with status 'queued'

**Endpoint Flow**:
1. Validate PDF file type
2. Validate user exists
3. Validate course exists and belongs to user
4. Read file bytes into memory
5. Upload PDF to Supabase Storage
6. Get page count (quick check)
7. Create `course_material` record with status 'uploading'
8. Start background task (`process_pdf_background`)
9. Return immediately with status 'queued'

**Background Processing** (handled by `pdf_processor.py`):
- Converts PDF pages to images (300 DPI, JPEG format)
- Processes pages in parallel (max 5 concurrent requests)
- For each page:
  - Convert PIL Image to bytes
  - Analyze using `analyze_pdf_page()` (async)
  - Save to `page_analyses` table
- Updates status to 'processing', then 'completed' or 'error'

**Key Features**:
- Async endpoint (`async def`)
- Background processing (no timeouts for large PDFs)
- Parallel page analysis (5 pages at once)
- Rate limit protection (semaphore-based)
- File validation (PDF only)
- Error handling with HTTPException
- Continues processing even if individual pages fail
- Immediate response with queued status

**Form Parameters**:
- `file`: PDF file (required, via multipart/form-data)
- `course_id`: Course ID (required - must exist)
- `user_id`: User ID (required)

**Response Status Values**:
- `queued`: Upload successful, processing started
- `uploading`: PDF uploaded, material record created
- `processing`: Background task running
- `completed`: All pages processed successfully
- `error`: Processing failed

**Dependencies**: 
- `fastapi` - Web framework (with BackgroundTasks)
- `pdf2image` - PDF to image conversion
- `pillow` - Image processing
- `app.services.pdf_processor` - Background processing service
- `app.services.analyzer` - Analysis service
- `app.services.storage` - Storage service
- `app.models.schemas` - Response models

**Usage**: Endpoint accessible at `POST /api/upload` when FastAPI app is running

---

### Backend Directory Structure

**Purpose**: Organized folder structure following FastAPI best practices and project requirements.

**Structure**:
```
backend/app/
├── __init__.py           # Package initialization
├── main.py              # FastAPI entry point
├── api/
│   ├── __init__.py
│   └── endpoints.py     # API route handlers
├── services/
│   ├── __init__.py
│   ├── analyzer.py      # Multimodal analysis service (async)
│   ├── pdf_processor.py  # Background PDF processing with parallel page analysis
│   └── storage.py       # Supabase operations
├── core/
│   ├── __init__.py
│   └── config.py        # Configuration management
└── models/
    ├── __init__.py
    └── schemas.py        # Pydantic models
```

**Dependencies**: Follows FastAPI application structure patterns

---