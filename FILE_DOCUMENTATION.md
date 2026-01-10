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