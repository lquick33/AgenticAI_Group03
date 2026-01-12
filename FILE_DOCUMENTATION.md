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

### `frontend/components/dashboard/upload-dialog.tsx`

**Purpose**: Client-side dialog component for uploading course materials (PDF files) to existing or newly created courses.

**Key Components**:
- **Dialog UI**: Uses shadcn/ui Dialog component for modal interface
- **Mode Selection**: Toggle between "Select Existing" course or "Create New" course
- **Course Selection**: Dropdown to select from existing courses (using Select component)
- **Course Creation Form**: Form fields for creating new course (title, description, exam_date)
- **File Upload**: File input for PDF file selection with validation
- **API Integration**: 
  - Creates courses via Supabase client
  - Uploads PDF files to backend API endpoint (`/api/upload`)
- **State Management**: 
  - Form state via React Hook Form
  - Loading states during upload
  - Error and success message display

**Key Features**:
- **Dual Mode**: Switch between selecting existing course or creating new one
- **Form Validation**: Required fields validation (course selection/creation, PDF file)
- **File Type Validation**: Only accepts PDF files
- **Loading States**: Shows loading spinner during upload process
- **Error Handling**: Displays error messages for failed operations
- **Success Feedback**: Shows success message before closing dialog
- **Auto Refresh**: Reloads page after successful upload to show new course/material

**Key Functions**:
- `createCourse(data: CourseFormData)`: Creates a new course in Supabase
- `uploadFile(courseId: string, file: File)`: Uploads PDF to backend API
- `onSubmit(data: CourseFormData)`: Handles form submission and orchestrates course creation + file upload

**Dependencies**: 
- `react-hook-form` - Form state management
- `@/components/ui/dialog` - Dialog modal component
- `@/components/ui/select` - Course selection dropdown
- `@/components/ui/button`, `@/components/ui/input`, `@/components/ui/label` - UI components
- `@/lib/supabase/client` - Supabase client for course creation
- `lucide-react` - Icons (Upload, Loader2, Plus)

**Environment Variables**:
- `NEXT_PUBLIC_API_URL` - Backend API URL (defaults to `http://localhost:8000` if not set)

**Usage**: 
```tsx
import { UploadDialog } from '@/components/dashboard/upload-dialog'

<UploadDialog courses={coursesList} />
```

**Props**:
- `courses: Course[]` - Array of existing courses for selection dropdown

**User Flow**:
1. User clicks "Upload Material" button (triggers dialog)
2. User chooses to select existing course or create new one
3. If creating new: Fill in course form (title, description, exam_date)
4. Select PDF file to upload
5. Click "Upload" button
6. System creates course (if new) and uploads PDF to backend
7. Backend processes PDF in background (multimodal analysis)
8. Dialog shows success message and closes
9. Page refreshes to show new course/material

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/page.tsx` - Dashboard page that uses this component
- `backend/app/api/endpoints.py` - Backend upload endpoint that receives the file
- `frontend/types/index.ts` - Course type definition

---

### `frontend/components/dashboard/sidebar.tsx`

**Purpose**: Client-side sidebar navigation component for the dashboard, using the shadcn sidebar structure with TeamSwitcher, collapsible navigation items, and projects section.

**Key Components**:
- **TeamSwitcher**: Brand/team selector in header (currently shows "Lernkompanien")
- **NavMainCollapsible**: Main navigation with collapsible submenus (Dashboard, Kurse with sub-items, Quick Chat, Einstellungen with sub-items)
- **NavProjects**: Quick access to specific courses/projects
- **NavUser**: User profile display with avatar, name, and email
- **SidebarRail**: Visual rail indicator for collapsed state
- **Responsive**: Icon-only collapsed mode on mobile/desktop

**Key Features**:
- Uses Next.js `Link` component for client-side navigation
- Active route detection using `usePathname()` hook
- Integrates with shadcn/ui Sidebar components
- User data passed from server component (dashboard page)
- Branding: "Lernkompanien" with SparklesIcon

**Key Functions**:
- Navigation items with active state based on current pathname
- Quick Chat button linking to `/dashboard/chat` (to be created)
- Kurse link to `/dashboard/courses` (to be created)

**Dependencies**: 
- `next/navigation` - Link and usePathname for routing
- `@/components/ui/sidebar` - shadcn/ui sidebar components (SidebarProvider, SidebarRail, etc.)
- `@/components/nav-main-collapsible` - Navigation with collapsible submenus
- `@/components/nav-projects` - Projects/courses quick access
- `@/components/nav-user` - User profile component
- `@/components/team-switcher` - Team/brand selector
- `lucide-react` - Icons (Sparkles, Bot, BookOpen, etc.)

**Usage**: 
```tsx
import { DashboardSidebar } from '@/components/dashboard/sidebar'

<DashboardSidebar user={userData} variant="inset" />
```

**Props**:
- `user: { name: string; email: string; avatar: string }` - User data for sidebar display

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/page.tsx` - Dashboard page that uses this sidebar
- `frontend/components/ui/sidebar.tsx` - Base sidebar component from shadcn/ui
- `frontend/components/nav-main-collapsible.tsx` - Collapsible navigation component
- `frontend/components/team-switcher.tsx` - Team switcher component
- `frontend/components/nav-projects.tsx` - Projects navigation component

---

### `frontend/components/nav-main-collapsible.tsx`

**Purpose**: Navigation component that supports collapsible submenus for sidebar navigation items.

**Key Components**:
- **Collapsible Items**: Navigation items with submenus that can be expanded/collapsed
- **Active State**: Highlights active routes and automatically opens parent items if child is active
- **Submenu Support**: Renders nested navigation items using SidebarMenuSub components
- **Link Integration**: Uses Next.js Link for client-side navigation

**Key Features**:
- Supports both simple navigation items (no submenu) and collapsible items (with submenu)
- Automatic active state detection based on pathname
- Chevron icon rotates when submenu is open
- Type-safe with TypeScript

**Dependencies**: 
- `@/components/ui/collapsible` - Collapsible component from shadcn/ui
- `@/components/ui/sidebar` - SidebarMenuSub, SidebarMenuSubButton, etc.
- `next/navigation` - Link and usePathname
- `lucide-react` - ChevronRight icon

**Usage**: Used by DashboardSidebar component

---

### `frontend/components/team-switcher.tsx`

**Purpose**: Team/brand switcher component for sidebar header, allowing users to switch between different teams or workspaces.

**Key Components**:
- **Dropdown Menu**: Shows current team and allows switching
- **Team Display**: Shows team logo, name, and plan
- **Team List**: Dropdown with all available teams
- **Keyboard Shortcuts**: Number shortcuts for quick team switching

**Key Features**:
- Currently configured for single team ("Lernkompanien")
- Can be extended to support multiple teams/workspaces
- Responsive: adjusts dropdown position on mobile vs desktop
- Visual team logo/icon display

**Dependencies**: 
- `@/components/ui/dropdown-menu` - Dropdown menu component
- `@/components/ui/sidebar` - SidebarMenu, SidebarMenuButton
- `lucide-react` - ChevronsUpDown icon

**Usage**: Used in DashboardSidebar header

**Future Enhancement**: Can be extended to fetch teams from Supabase or support workspace switching

---

### `frontend/components/nav-projects.tsx`

**Purpose**: Quick access navigation component for projects/courses in the sidebar.

**Key Components**:
- **Project List**: Displays list of projects/courses with icons
- **Group Label**: "Kurse" label for the section
- **Link Navigation**: Uses Next.js Link for client-side navigation

**Key Features**:
- Currently shows sample courses (KI Grundlagen, Programmierung, Datenbanken)
- Hidden when sidebar is in icon-only mode
- Simple list format with icons

**Dependencies**: 
- `@/components/ui/sidebar` - SidebarGroup, SidebarMenu, etc.
- `next/link` - Next.js Link component
- `lucide-react` - Icons for projects

**Usage**: Used in DashboardSidebar to show quick course access

**Future Enhancement**: Will fetch actual courses from Supabase and display user's courses

---

### `frontend/components/dashboard/kpi-cards.tsx`

**Purpose**: Server component displaying Key Performance Indicator (KPI) cards for learning metrics with dummy data.

**Key Components**:
- **Four KPI Cards**: 
  1. Aktive Kurse (Active Courses) - Shows number of active courses
  2. Abgeschlossene Lerneinheiten (Completed Units) - Shows completed learning units
  3. Gesamtzeit gelernt (Total Study Time) - Shows total study hours
  4. Durchschnittlicher Fortschritt (Average Progress) - Shows average progress percentage
- **Trend Indicators**: Each card shows trend (e.g., "+2", "+5%") with up/down arrows
- **Responsive Grid**: Adapts from 1 column (mobile) to 4 columns (desktop)

**Key Features**:
- Dummy data structure for testing layout
- Trend badges with icons (TrendingUpIcon)
- Card descriptions and additional info
- Responsive design using Tailwind container queries (`@container/card`)
- Gradient backgrounds for visual appeal

**Dummy Data Structure**:
```typescript
{
  activeCourses: { value: "5", trend: "+2", description: "Kurse diesen Monat" },
  completedUnits: { value: "23", trend: "+5", description: "Diese Woche abgeschlossen" },
  totalStudyTime: { value: "42.5h", trend: "+3.2h", description: "Diese Woche gelernt" },
  averageProgress: { value: "78%", trend: "+5%", description: "Durchschnitt über alle Kurse" }
}
```

**Dependencies**: 
- `@/components/ui/card` - Card components (CardHeader, CardTitle, etc.)
- `@/components/ui/badge` - Badge component for trends
- `lucide-react` - Icons (TrendingUpIcon, TrendingDownIcon)

**Usage**: 
```tsx
import { KPICards } from '@/components/dashboard/kpi-cards'

<KPICards />
```

**Future Integration**: Will be updated to fetch real data from Supabase (courses count, learning units, study time, progress calculations)

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/page.tsx` - Dashboard page that displays KPI cards
- `frontend/types/index.ts` - LearningUnit and Course types for future data integration

---

### `frontend/components/dashboard/progress-chart.tsx`

**Purpose**: Client component displaying a line chart showing learning progress over time with dummy data.

**Key Components**:
- **Area Chart**: Dual-line area chart showing progress vs. target
- **Time Range Selector**: Toggle between "Last 3 months", "Last 30 days", "Last 7 days"
- **Responsive**: Mobile-friendly with dropdown selector on small screens
- **Chart Tooltip**: Interactive tooltips showing exact values on hover

**Key Features**:
- Uses Recharts library for chart rendering
- Dummy data generated for last 90 days
- Two data series: `progress` (actual) and `target` (goal)
- Progress line: solid with gradient fill
- Target line: dashed with different gradient
- Responsive time range selection (mobile uses dropdown, desktop uses toggle buttons)
- Chart automatically adjusts data based on selected time range

**Dummy Data Generation**:
- Generates 90 days of data points
- Progress: Random values between 60-100%
- Target: Random values between 70-90%
- Dates formatted using `date-fns`

**Dependencies**: 
- `recharts` - Chart library (AreaChart, Area, XAxis, etc.)
- `date-fns` - Date formatting utilities
- `@/components/ui/chart` - shadcn/ui chart wrapper components
- `@/components/ui/card` - Card container
- `@/components/ui/select` - Dropdown for mobile
- `@/components/ui/toggle-group` - Toggle buttons for desktop
- `@/hooks/use-mobile` - Mobile detection hook

**Usage**: 
```tsx
import { ProgressChart } from '@/components/dashboard/progress-chart'

<ProgressChart />
```

**Future Integration**: Will fetch real progress data from Supabase `learning_units` table, calculating actual completion rates and comparing to planned targets.

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/page.tsx` - Dashboard page that displays the chart
- `frontend/types/index.ts` - LearningUnit type for future data integration

---

### `frontend/components/dashboard/learning-units-table.tsx`

**Purpose**: Client component displaying a table of learning units with dummy data, adapted from shadcn dashboard-01 data-table.

**Key Components**:
- **Table Columns**:
  - Checkbox (for multi-select)
  - Lerneinheit (Topic name)
  - Kurs (Course name)
  - Status (Badge with icon: Abgeschlossen, In Bearbeitung, Übersprungen, Verschoben)
  - Fortschritt (Progress percentage)
  - Verständnis (Comprehension score or "N/A")
  - Geplant für (Planned date and time)
  - Actions (Dropdown menu)
- **Row Selection**: Checkbox selection for bulk actions (future feature)
- **Status Badges**: Color-coded badges with icons for different statuses
- **Actions Menu**: Dropdown with options (Bearbeiten, Details, Löschen)

**Key Features**:
- Dummy data based on `LearningUnit` type from `@/types`
- Status visualization with icons (CheckCircle2Icon for completed, LoaderIcon for in progress)
- Date formatting using `date-fns`
- Responsive table design
- Selection counter showing selected rows

**Dummy Data**:
- 6 sample learning units with various statuses (completed, planned, skipped)
- Mix of different courses (KI Grundlagen, Programmierung, Datenbanken)
- Different progress values (0%, 45%, 100%)
- Comprehension scores where applicable

**Status Mapping**:
- `completed` → "Abgeschlossen" (green checkmark icon)
- `planned` → "In Bearbeitung" (spinning loader icon)
- `skipped` → "Übersprungen" (plain badge)
- `rescheduled` → "Verschoben" (plain badge)

**Dependencies**: 
- `@/components/ui/table` - Table components (Table, TableHeader, TableBody, etc.)
- `@/components/ui/badge` - Badge component for status
- `@/components/ui/checkbox` - Checkbox for row selection
- `@/components/ui/dropdown-menu` - Actions menu
- `date-fns` - Date formatting
- `lucide-react` - Icons (CheckCircle2Icon, LoaderIcon, MoreVerticalIcon)
- `@/types` - LearningUnit type definition

**Usage**: 
```tsx
import { LearningUnitsTable } from '@/components/dashboard/learning-units-table'

<LearningUnitsTable />
```

**Future Integration**: 
- Fetch real data from Supabase `learning_units` table
- Add filtering and sorting capabilities
- Implement bulk actions (delete, mark as completed, etc.)
- Add pagination for large datasets
- Link to course detail pages

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/page.tsx` - Dashboard page that displays the table
- `frontend/types/index.ts` - LearningUnit type definition

---

### `frontend/app/(dashboard)/dashboard/page.tsx` (Updated)

**Purpose**: Main dashboard page integrating all dashboard components (Sidebar, KPI Cards, Progress Chart, Learning Units Table) with authentication.

**Key Components**:
- **Authentication**: Uses `requireAuth()` to ensure user is logged in
- **User Data Fetching**: Gets user data from Supabase for sidebar
- **Layout Structure**: 
  - `SidebarProvider` - Wraps entire dashboard for sidebar state management
  - `DashboardSidebar` - Left sidebar navigation
  - `SidebarInset` - Main content area
  - `KPICards` - Top KPI metrics
  - `ProgressChart` - Middle progress visualization
  - `LearningUnitsTable` - Bottom learning units table

**Key Features**:
- Server Component for authentication and data fetching
- Integrates all dashboard components in a cohesive layout
- Responsive design with sidebar that collapses on mobile
- Error handling for user data fetching failures

**Layout Structure**:
```tsx
<SidebarProvider>
  <DashboardSidebar user={userData} />
  <SidebarInset>
    <KPICards />
    <ProgressChart />
    <LearningUnitsTable />
  </SidebarInset>
</SidebarProvider>
```

**Dependencies**: 
- `@/lib/auth` - Authentication utilities (requireAuth)
- `@/lib/supabase/server` - Server-side Supabase client
- `@/components/dashboard/sidebar` - Dashboard sidebar component
- `@/components/dashboard/kpi-cards` - KPI cards component
- `@/components/dashboard/progress-chart` - Progress chart component
- `@/components/dashboard/learning-units-table` - Learning units table component
- `@/components/ui/sidebar` - SidebarProvider and SidebarInset

**Usage**: Accessible at `/dashboard` route (protected, requires authentication)

**User Flow**:
1. User navigates to `/dashboard`
2. Server checks authentication (redirects to `/login` if not authenticated)
3. Fetches user data from Supabase
4. Renders dashboard with sidebar and all components
5. All components display dummy data (ready for backend integration)

**Future Enhancements**:
- Fetch real KPI data from Supabase
- Load actual progress data for chart
- Display real learning units from database
- Add loading states during data fetching
- Add error boundaries for component failures

**Related Files**: 
- All dashboard component files (sidebar, kpi-cards, progress-chart, learning-units-table)
- `frontend/lib/auth.ts` - Authentication utilities

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

## Course Management Components

### `frontend/components/courses/create-course-dialog.tsx`

**Purpose**: Dialog component for creating new courses with form validation.

**Key Components**:
- React Hook Form with Zod validation
- Form fields: title (required), description (optional), exam_date (optional)
- Supabase client integration for course creation
- Error handling and loading states
- Redirects to course detail page after successful creation

**Key Features**:
- Client Component ("use client")
- Form validation using Zod schema
- Supabase insert operation into `courses` table
- Automatic redirect to `/dashboard/courses/[id]` after creation
- Error messages displayed to user

**Form Schema**:
```typescript
{
  title: string (required, min 1 character)
  description?: string (optional)
  exam_date?: string (optional, date format)
}
```

**Dependencies**: 
- `react-hook-form` - Form handling
- `zod` - Schema validation
- `@hookform/resolvers/zod` - Zod resolver for react-hook-form
- `@/lib/supabase/client` - Supabase client for database operations
- `@/components/ui/dialog` - Dialog component
- `@/components/ui/button`, `@/components/ui/input`, `@/components/ui/label` - Form components
- `next/navigation` - Router for navigation

**Usage**: 
```tsx
import { CreateCourseDialog } from '@/components/courses/create-course-dialog'

<CreateCourseDialog />
```

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/page.tsx` - Uses this component
- `frontend/types/index.ts` - Course type definition

---

### `frontend/components/courses/courses-table.tsx`

**Purpose**: Table component displaying all courses with KPIs and statistics.

**Key Components**:
- Displays course title, description, material count, progress, last updated date
- Progress bar visualization
- Clickable rows that navigate to course detail page
- Empty state when no courses exist

**Key Features**:
- Client Component ("use client")
- Progress calculation: `(analyzed_pages / total_pages) * 100`
- Date formatting for German locale
- Badge display for material count
- Responsive table layout

**Table Columns**:
- Titel (Title)
- Beschreibung (Description)
- Materialien (Material count badge)
- Progress (Progress bar with percentage)
- Letztes Update (Last updated date)
- Aktionen (Action button to open course)

**Dependencies**: 
- `@/components/ui/table` - Table components
- `@/components/ui/badge` - Badge for material count
- `@/components/ui/button` - Action button
- `next/link` - Navigation
- `lucide-react` - Icons (ArrowRight)
- `@/types` - CourseWithStats type

**Usage**: 
```tsx
import { CoursesTable } from '@/components/courses/courses-table'

<CoursesTable courses={coursesWithStats} />
```

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/page.tsx` - Uses this component
- `frontend/types/index.ts` - CourseWithStats type definition

---

### `frontend/components/courses/upload-section.tsx`

**Purpose**: Component for uploading PDF files to a course using the `/api/upload` endpoint.

**Key Components**:
- File input with drag-and-drop styling
- PDF file validation
- Upload button with loading state
- Error and success message display
- Automatic page refresh after successful upload

**Key Features**:
- Client Component ("use client")
- File type validation (PDF only)
- FormData construction for API request
- Integration with `/api/upload` POST endpoint
- Loading states during upload
- Error handling with user-friendly messages
- Automatic refresh after successful upload

**Upload Flow**:
1. User selects PDF file
2. File validation (PDF type check)
3. FormData created with `file`, `user_id`, `course_id`
4. POST request to `${NEXT_PUBLIC_API_URL}/api/upload`
5. Success message displayed
6. Page refresh to show new material

**Dependencies**: 
- `@/lib/supabase/client` - Supabase client for user authentication
- `@/components/ui/button` - Upload button
- `lucide-react` - Icons (Upload, Loader2)
- `next/navigation` - Router for refresh
- Environment variable: `NEXT_PUBLIC_API_URL`

**Usage**: 
```tsx
import { UploadSection } from '@/components/courses/upload-section'

<UploadSection courseId={courseId} />
```

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/[id]/page.tsx` - Uses this component
- `backend/app/api/endpoints.py` - Upload API endpoint

---

### `frontend/components/courses/course-materials-list.tsx`

**Purpose**: Table component displaying all uploaded course materials with their status.

**Key Components**:
- Displays material file name, page count, processing status, upload date
- Status badges (uploading, processing, completed, error)
- Empty state when no materials exist

**Key Features**:
- Client Component ("use client")
- Status badge variants based on `processing_status`
- Date formatting for German locale
- Responsive table layout

**Table Columns**:
- Dateiname (File name)
- Seiten (Page count)
- Status (Processing status badge)
- Hochgeladen am (Upload date)

**Status Badge Variants**:
- `uploading`: Outline badge
- `processing`: Secondary badge
- `completed`: Default badge
- `error`: Destructive badge

**Dependencies**: 
- `@/components/ui/table` - Table components
- `@/components/ui/badge` - Status badges
- `@/types` - CourseMaterial type

**Usage**: 
```tsx
import { CourseMaterialsList } from '@/components/courses/course-materials-list'

<CourseMaterialsList materials={materials} />
```

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/[id]/page.tsx` - Uses this component
- `frontend/types/index.ts` - CourseMaterial type definition

---

### `frontend/components/courses/exam-date-editor.tsx`

**Purpose**: Client Component to view and update the exam date of a course with a calendar picker and Save action.

**Key Components**:
- Uses shadcn `Calendar` component (`components/ui/calendar`)
- Save button triggers Supabase update of `courses.exam_date`
- Displays errors and loading state, then refreshes page

**Props**:
- `courseId: string` - Target course
- `initialDate?: string | null` - Pre-filled date from DB

**Flow**:
1. User selects date in calendar
2. Clicks "Prüfungsdatum speichern"
3. Supabase `update` on `courses` sets `exam_date` (ISO date)
4. `router.refresh()` to show updated date

**Dependencies**:
- `@/lib/supabase/client` - Supabase client
- `@/components/ui/calendar`, `@/components/ui/button`
- `next/navigation` - router refresh

**Usage**:
```tsx
<ExamDateEditor courseId={id} initialDate={course.exam_date} />
```

**Related Files**:
- `frontend/app/(dashboard)/dashboard/courses/[id]/page.tsx` - Uses this component
- `frontend/components/ui/calendar.tsx` - Calendar UI

---

### `frontend/components/calendar-01.tsx`

**Purpose**: Example calendar block (shadcn `calendar-01`) showing a single-date selector with default date.

**Key Components**:
- Wraps `Calendar` from `components/ui/calendar`
- Manages local state for selected date

**Usage**:
```tsx
import Calendar01 from '@/components/calendar-01'
<Calendar01 />
```

**Note**: Primarily a reference/demo; production use is via `ExamDateEditor`.

---

### `frontend/app/(dashboard)/dashboard/courses/page.tsx`

**Purpose**: Server Component page displaying the courses overview with table and create course dialog.

**Key Components**:
- Server-side data fetching from Supabase
- Courses query with aggregations (material count, analyzed pages, total pages)
- Integration of `CoursesTable` and `CreateCourseDialog` components
- Sidebar layout consistent with dashboard

**Key Features**:
- Server Component for authentication and data fetching
- Supabase query with JOINs to calculate statistics:
  - Material count per course
  - Analyzed pages count
  - Total pages count
  - Last updated timestamp
- Error handling for user and course data fetching
- Sidebar integration with `DashboardSidebar`

**Data Transformation**:
- Transforms raw Supabase query results into `CourseWithStats` type
- Calculates statistics from nested `course_materials` and `page_analyses` arrays
- Determines last updated date from material creation dates

**Dependencies**: 
- `@/lib/auth` - Authentication utilities (requireAuth)
- `@/lib/supabase/server` - Server-side Supabase client
- `@/components/dashboard/sidebar` - Dashboard sidebar
- `@/components/courses/courses-table` - Courses table component
- `@/components/courses/create-course-dialog` - Create course dialog
- `@/components/ui/sidebar` - SidebarProvider and SidebarInset
- `@/types` - CourseWithStats type

**Usage**: Accessible at `/dashboard/courses` route (protected, requires authentication)

**User Flow**:
1. User navigates to `/dashboard/courses`
2. Server checks authentication
3. Fetches user data and courses with statistics from Supabase
4. Renders courses table with KPIs
5. User can create new course via dialog
6. User can click on course to navigate to detail page

**Related Files**: 
- `frontend/components/courses/courses-table.tsx` - Table component
- `frontend/components/courses/create-course-dialog.tsx` - Create dialog
- `frontend/types/index.ts` - CourseWithStats type

---

### `frontend/app/(dashboard)/dashboard/courses/[id]/page.tsx`

**Purpose**: Server Component page displaying course detail view with upload functionality and materials list.

**Key Components**:
- Server-side data fetching for course details and materials
- Course info card with KPIs (material count, total pages, progress)
- Upload section for PDF files
- Materials list table
- Sidebar layout consistent with dashboard

**Key Features**:
- Server Component for authentication and data fetching
- Course validation (checks if course exists and belongs to user)
- 404 handling if course not found
- Statistics calculation:
  - Material count
  - Total pages from all materials
  - Analyzed pages count from `page_analyses` table
  - Progress percentage
- Exam date display if available

**Sections**:
1. **Course Info Card**: Title, description, KPIs, exam date
2. **Upload Section**: File upload component
3. **Materials List**: Table of all uploaded materials with status

**Dependencies**: 
- `@/lib/auth` - Authentication utilities (requireAuth)
- `@/lib/supabase/server` - Server-side Supabase client
- `@/components/dashboard/sidebar` - Dashboard sidebar
- `@/components/courses/upload-section` - Upload component
- `@/components/courses/course-materials-list` - Materials list component
- `@/components/ui/card` - Course info card
- `@/components/ui/badge` - Status badges
- `@/components/ui/sidebar` - SidebarProvider and SidebarInset
- `next/navigation` - notFound() for 404 handling
- `@/types` - Course and CourseMaterial types

**Usage**: Accessible at `/dashboard/courses/[id]` route (protected, requires authentication)

**User Flow**:
1. User navigates to `/dashboard/courses/[id]`
2. Server checks authentication and validates course ownership
3. Fetches course details and materials from Supabase
4. Calculates statistics (material count, pages, progress)
5. Renders course info, upload section, and materials list
6. User can upload new PDF files
7. User can view uploaded materials and their processing status

**Related Files**: 
- `frontend/components/courses/upload-section.tsx` - Upload component
- `frontend/components/courses/course-materials-list.tsx` - Materials list
- `frontend/types/index.ts` - Course and CourseMaterial types

---

### `frontend/types/index.ts` (Updated)

**Purpose**: TypeScript type definitions for database entities, extended with course management types.

**New/Updated Types**:

**`CourseMaterial` (Updated)**:
- Added `user_id: string`
- Changed `status` to `processing_status: 'uploading' | 'processing' | 'completed' | 'error'`
- Added `error_message?: string | null`
- Changed `uploaded_at` to `created_at: string`
- Matches Supabase schema exactly

**`CourseWithStats` (New)**:
- Extends `Course` interface
- Adds statistics fields:
  - `material_count: number` - Number of course materials
  - `analyzed_pages: number` - Number of analyzed pages
  - `total_pages: number` - Total pages across all materials
  - `last_updated: string | null` - Last material upload date

**Dependencies**: None (standalone type definitions)

**Usage**: Import types in components:
```typescript
import type { Course, CourseMaterial, CourseWithStats } from '@/types'
```

**Related Files**: 
- All course management components use these types
- Database schema in `backend/supabase/migrations/20260110111927_initial_schema.sql`

---