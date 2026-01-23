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

### `supabase/migrations/20260113000000_add_summary_to_course_materials.sql`

**Purpose**: Migration file that extends the `course_materials` table with a `summary` column used to store a global, LLM-generated topics overview for each uploaded lecture.

**Key Components**:
- **New Column**: Adds `summary TEXT` to `course_materials`
- **Intended Use**:
  - Stores a JSON-encoded summary object with overall lecture summary and main topics
  - Populated asynchronously by the PDF processing pipeline after all pages have been analyzed
  - Serves as a central entry point for:
    - Course/topic tracking across materials
    - Future Meta Agent planning (Themenplanung, Wissensstände)
    - Initial overview for the Tutor Agent in the Study Reader

**Dependencies**: Builds on the initial schema migration (`20260110111927_initial_schema.sql`) and expects the `course_materials` table to exist.

**Usage**: Apply via Supabase SQL editor or CLI as part of the normal migration flow (`supabase db push`).

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
- `generate_material_summary(page_data: Sequence[dict]) -> str`: Generate global topics summary from per-page analyses
- `generate_material_filename(page_one_summary: str) -> str`: Generate professional filename based on page 1 summary
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
6. Generate global material summary (if pages analyzed successfully)
7. Update final status based on results
8. Generate and update professional filename based on page 1 summary (if completed successfully)

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

### `backend/app/services/observability.py`

**Purpose**: Langfuse Observability Service für zentrales Token-Tracking und Observability von LLM-Calls.

**Key Components**:
- **`get_langfuse_client()`**: Erstellt oder gibt Langfuse Client-Instanz zurück (verwendet `get_client()` aus Langfuse SDK)
- **`create_callback_handler()`**: Erstellt Langfuse CallbackHandler für LangChain Integration
  - Trackt automatisch: Token Usage, Model Parameters, Input/Output Messages, Latency, Errors
  - Unterstützt user_id, session_id, metadata für Trace-Gruppierung
- **`extract_token_usage()`**: Extrahiert Token-Usage aus LLM Response (optional, für Debugging)
- **`flush_langfuse()`**: Flusht pending Langfuse Events (wichtig für short-lived processes)
- **`shutdown_langfuse()`**: Graceful shutdown des Langfuse Clients

**Features**:
- Automatisches Token-Tracking über LangChain CallbackHandler
- Automatische Kostenberechnung (wenn Modell-Preise in Langfuse konfiguriert)
- Graceful Degradation (funktioniert auch ohne Langfuse-Konfiguration)
- Feature Flag über `LANGFUSE_ENABLED` in config.py

**Dependencies**: 
- `langfuse>=3.10.1` (in requirements.txt)
- Environment Variables: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `LANGFUSE_ENABLED`

**Usage**: 
- Wird automatisch vom TutorAgent verwendet (via `create_callback_handler()`)
- Wird in API Endpoints für Trace-Wrapping verwendet (`/chat/initiate`, `/chat/message`)

**Related Files**:
- `backend/app/core/config.py` - Langfuse Konfiguration
- `backend/app/agents/tutor/tutor_agent.py` - Verwendet CallbackHandler
- `backend/app/api/endpoints.py` - Verwendet Langfuse Tracing

---

### `backend/app/services/storage.py`

**Purpose**: Supabase Storage and Database operations for file uploads and analysis storage.

**Key Components**:
- `get_supabase_client() -> Client`: Singleton Supabase client initialization
- `upload_pdf_to_storage(file_bytes, filename, user_id) -> str`: Upload PDF to Supabase Storage bucket
- `create_course_material(...) -> dict`: Create course_material record in database
- `update_processing_status(material_id, status, error_message) -> None`: Update processing status
- `save_page_analysis(course_material_id, page_number, analysis, user_id) -> dict`: Save analysis to `page_analyses` table
- `update_course_material_filename(material_id, filename) -> None`: Update the display filename in `course_materials` table

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

**Additional Endpoints**:
- `PUT /api/materials/{material_id}`: Update course material data (currently supports filename updates)
  - Validates material ownership
  - Request body: `{ "file_name": string }`
  - Returns: `MaterialResponse` with updated material data

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

### `frontend/components/courses/editable-filename.tsx`

**Purpose**: Inline editable filename component for course materials with dezent UI design.

**Key Components**:
- `EditableFilename` component with double-click to edit functionality
- Inline editing mode with minimal UI (no visible border, only cursor)
- Checkmark icon for saving (appears on hover)
- Keyboard shortcuts: Enter to save, Escape to cancel
- Optimistic updates with error rollback

**Key Features**:
- **Double-click activation**: Double-click on filename to enter edit mode
- **Dezent UI**: Input without visible border, only cursor visible
- **Auto-focus and select**: Automatically focuses and selects all text when entering edit mode
- **Checkmark icon**: Small checkmark icon (3px) appears on hover for saving
- **Keyboard shortcuts**: 
  - Enter: Save changes
  - Escape: Cancel editing
- **Loading state**: Shows spinner while saving
- **Error handling**: Toast notifications for success/error, reverts to original on error
- **Optimistic updates**: Updates parent component immediately on success

**Props**:
- `materialId: string` - Course material ID
- `userId: string` - User ID for authorization
- `initialFilename: string` - Current filename
- `onUpdate?: (newFilename: string) => void` - Callback when filename is updated

**Dependencies**: 
- `@/lib/api/materials` - API client for updating filename
- `sonner` - Toast notifications
- `lucide-react` - Icons (Check, Loader2)

**Usage**: Used in `course-materials-list.tsx` for each material row

**Related Files**: 
- `frontend/lib/api/materials.ts` - API client function
- `frontend/components/courses/course-materials-list.tsx` - Parent component

---

### `frontend/lib/api/materials.ts`

**Purpose**: API client functions for course materials operations.

**Key Components**:
- `updateMaterialFilename(materialId, filename, userId)`: Updates the filename of a course material

**Key Features**:
- RESTful API communication with backend
- Error handling with descriptive messages
- Type-safe function signatures

**Dependencies**: 
- `process.env.NEXT_PUBLIC_API_URL` - Backend API URL

**Usage**: Imported by `EditableFilename` component

**Related Files**: 
- `backend/app/api/endpoints.py` - PUT /api/materials/{material_id} endpoint
- `frontend/components/courses/editable-filename.tsx` - Component using this API

---

### `frontend/components/courses/course-materials-list.tsx`

**Purpose**: Table component displaying all uploaded course materials with their status.

**Key Components**:
- Displays material file name (editable via double-click), page count, processing status, upload date
- Status badges (uploading, processing, completed, error)
- Empty state when no materials exist
- EditableFilename component for inline filename editing
- Local state management for optimistic updates

**Key Features**:
- Client Component ("use client")
- **Inline filename editing**: Double-click on filename to edit (via EditableFilename component)
- Status badge variants based on `processing_status`
- Date formatting for German locale
- Responsive table layout
- Optimistic UI updates when filename is changed

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
- `@/components/courses/editable-filename` - Editable filename component
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

**`ChatMessage` (New)**:
- Interface for chat messages in study sessions
- Fields: `id`, `role` ('user' | 'assistant' | 'system'), `content`, `timestamp`

**`PageAnalysisData` (New)**:
- Interface for page analysis data retrieved from API
- Fields: `summary`, `key_terms` (string[]), `exam_questions` (string[]), `diagram_description?` (optional)

---

## Study Session Components

### `backend/app/agents/base.py`

**Purpose**: Base agent class for all LangGraph agents, providing consistent interface and state management.

**Key Components**:
- `State(MessagesState)`: Base state class extending LangGraph MessagesState
- `BaseAgent(ABC)`: Abstract base class with:
  - `_build_graph()`: Abstract method for graph construction
  - `compile_graph()`: Compiles workflow with checkpointer/store
  - `run()`, `arun()`, `stream()`: Execution methods with thread persistence
  - `save_memory()`, `retrieve_memory()`: Long-term memory operations
  - `get_conversation_history()`: Retrieve conversation history
  - `add_system_message()`: System message handling

**Key Features**:
- Thread-based conversation persistence (thread_id)
- User-based memory storage (user_id)
- Automatic system message injection for new threads
- Checkpointer and Store support for state persistence
- Streaming support for real-time responses

**Dependencies**: 
- `langgraph` - Graph framework
- `langchain_core` - LLM integration
- `langgraph.checkpoint` - State persistence
- `langgraph.store` - Memory storage

**Usage**: All agents must inherit from `BaseAgent` and implement `_build_graph()`

**Related Files**: 
- `backend/app/agents/tutor/tutor_agent.py` - Tutor agent implementation
- `AGENT_DEVELOPMENT_RULES.md` - Development guidelines

---

### `backend/app/agents/tutor/tutor_agent.py`

**Purpose**: LangGraph Tutor Agent for study sessions that helps students understand lecture materials.

**Key Components**:
- `TutorState(State)`: Extends base State with `current_page`, `material_id`, `user_id`
- `StateAwareToolNode(ToolNode)`: Custom ToolNode that automatically injects state values (`material_id` → `course_material_id`, `current_page` → `page_number`, `user_id`) into tool calls to prevent LLM hallucination
- `TutorAgent(BaseAgent)`: Agent implementation with:
  - `GetPageAnalysisTool` integration
  - Graph structure: `agent` → `tools` → `agent` (loop until no tool calls)
  - Conditional routing based on tool calls
  - Personalized system prompts with language and personality config
  - **Langfuse Prompt Management**: Loads system prompts dynamically from Langfuse with fallback to hardcoded versions

**Graph Structure**:
1. `agent` node: Calls LLM with tools bound, injects state context into system prompt
2. `tools` node: Executes tool calls with automatic state injection (StateAwareToolNode)
3. Conditional edge: Routes back to `agent` if tools called, else `END`

**System Prompt** (Personalizable):
- **Role**: Personal professor for university students, explains at student-friendly level
- **Teaching Method**: Socratic method - asks questions before explaining, uses analogies, breaks concepts into steps
- **Language Support**: Configurable language (default: "de" for German, supports "en" for English)
- **Personality Traits** (configurable via `personality_config`):
  - `formality`: "formal" | "informal" | "balanced" (default: "balanced")
  - `humor`: "none" | "light" | "moderate" (default: "light")
  - `encouragement`: "reserved" | "moderate" | "enthusiastic" (default: "moderate")
- **Context Awareness**: Automatically receives current page number, material ID, and user ID from state
- **Tool Instructions**: Clear guidance on using `get_page_analysis` tool with automatic argument injection
- **Prompt Management**: 
  - System prompts are managed in Langfuse under `tutor-agent/system-prompt-de` and `tutor-agent/system-prompt-en`
  - Prompts use variables ({{formality_text}}, {{humor_text}}, {{encouragement_text}}) that are compiled at runtime
  - Automatic fallback to hardcoded prompts if Langfuse is unavailable or prompts cannot be loaded
  - Prompts can be updated in Langfuse UI without code changes

**Key Features**:
- **State Injection**: State information (`current_page`, `material_id`, `user_id`) automatically injected into LLM context via enhanced system prompt
- **Automatic Tool Argument Injection**: StateAwareToolNode automatically fills tool arguments from state, preventing LLM from hallucinating IDs
- **Personalization**: Configurable language and personality traits for personalized tutoring experience
- **Tool-based information retrieval**: Page analysis via GetPageAnalysisTool
- **Context-aware tutoring**: Based on slide content and current page
- **Continuous conversation**: Across pages (thread_id = material_id)
- **Streaming support**: Real-time responses via SSE

**Initialization Parameters**:
- `llm`: BaseChatModel (required)
- `name`: str (default: "TutorAgent")
- `system_prompt`: Optional[str] (if None, uses `_build_system_prompt()`)
- `checkpointer`: Optional[MemorySaver] (for conversation persistence)
- `language`: str (default: "de") - Communication language
- `personality_config`: Optional[Dict[str, str]] - Personality traits dict

**Methods**:
- `_build_system_prompt(language, personality_config)`: Loads system prompt from Langfuse or uses fallback, compiles with personality variables
- `_get_personality_texts(language, formality, humor, encouragement)`: Returns personality trait texts based on language and config
- `_build_system_prompt_fallback(language, formality, humor, encouragement)`: Builds hardcoded system prompt (fallback)
- `call_model(state)`: Calls LLM with state context injected into system message
- `_build_graph()`: Builds LangGraph workflow with StateAwareToolNode

**Dependencies**: 
- `app.agents.base` - BaseAgent class
- `app.tools.page_analysis_tool` - GetPageAnalysisTool
- `app.services.observability` - get_langfuse_client (for prompt management)
- `langgraph.prebuilt` - ToolNode base class
- `langgraph.checkpoint.memory` - MemorySaver for persistence

**Usage**: 
```python
agent = TutorAgent(
    llm=llm,
    language="de",
    personality_config={
        "formality": "balanced",
        "humor": "light",
        "encouragement": "moderate"
    },
    checkpointer=checkpointer
)
```

**Related Files**: 
- `backend/app/api/endpoints.py` - Chat endpoints that use this agent
- `backend/app/tools/page_analysis_tool.py` - Tool used by agent

---

### `backend/app/tools/page_analysis_tool.py`

**Purpose**: LangChain tool for retrieving structured page analysis data from the database.

**Key Components**:
- `GetPageAnalysisInput(BaseModel)`: Pydantic input schema with `course_material_id`, `page_number`, `user_id`
- `GetPageAnalysisTool`: Tool class with:
  - `_run()`: Synchronous execution
  - `_arun()`: Async execution
  - `to_langchain_tool()`: Converts to LangChain StructuredTool

**Key Features**:
- **Performance-Optimized**: Directly imports service function (no HTTP request to own backend)
- Returns JSON string with analysis data: `summary`, `key_terms`, `exam_questions`, `diagram_description`
- Error handling: Returns error JSON instead of raising exceptions
- Type-safe with Pydantic input validation

**Tool Description**:
- Clear description for LLM: "Retrieves structured analysis data for a specific page..."
- Helps LLM understand when to use this tool

**Dependencies**: 
- `app.services.storage` - `get_page_analysis()` service function
- `langchain_core.tools` - StructuredTool
- `pydantic` - Input validation

**Usage**: Converted to LangChain tool and bound to LLM in TutorAgent

**Related Files**: 
- `backend/app/services/storage.py` - Service function implementation
- `backend/app/agents/tutor/tutor_agent.py` - Agent that uses this tool

---

### `backend/app/tools/course_material_tool.py`

**Purpose**: LangChain tool for retrieving the overall summary of a course material from the `course_materials` table. This tool allows the Tutor Agent to access a JSON-encoded overview of the lecture topics, concepts, and key themes for the entire course material, which is especially useful when greeting a student for the first time.

**Key Components**:
- `GetCourseMaterialSummaryInput(BaseModel)`: Pydantic input schema with `course_material_id`, `user_id`
- `GetCourseMaterialSummaryTool`: Tool class with:
  - `_run()`: Synchronous execution method that calls `get_course_material_summary()` service function
  - `_arun()`: Async wrapper for `_run()`
  - `to_langchain_tool()`: Converts to LangChain StructuredTool for agent integration

**Key Features**:
- Retrieves the `summary` field from `course_materials` table
- Parses JSON-encoded summary data (falls back to plain text if not valid JSON)
- Returns structured data with error handling
- Used by TutorAgent when greeting students for the first time to provide context about lecture content
- Automatically injects `course_material_id` and `user_id` from agent state via `StateAwareToolNode`

**Tool Description**:
- Clear description for LLM: "Retrieves the overall summary of a course material..."
- Helps LLM understand when to use this tool (especially for first-time greetings)

**Dependencies**: 
- `app.services.storage` - `get_course_material_summary()` service function
- `langchain_core.tools` - StructuredTool
- `pydantic` - Input validation

**Usage**: Converted to LangChain tool and bound to LLM in TutorAgent. The agent is instructed to use this tool when greeting a student for the first time (no chat history) to get context about the lecture topics.

**Related Files**: 
- `backend/app/services/storage.py` - `get_course_material_summary()` service function implementation
- `backend/app/agents/tutor/tutor_agent.py` - TutorAgent that uses this tool
- `backend/app/api/endpoints.py` - Chat initiation endpoint that instructs agent to use this tool for first-time greetings

---

### `backend/app/services/storage.py` (Updated)

**New Functions**: `get_page_analysis()`, `get_page_analysis_id()`, and `get_course_material_summary()`

**`get_page_analysis()`**:

**Purpose**: Retrieves page analysis data from the `page_analyses` table.

**Function Signature**:
```python
def get_page_analysis(
    course_material_id: str,
    page_number: int,
    user_id: str
) -> dict
```

**Key Features**:
- Query Supabase `page_analyses` table with filters
- Returns structured dict with: `summary`, `key_terms`, `exam_questions`, `diagram_description`, `raw_analysis`
- User authorization via RLS (Row Level Security)
- Raises `ValueError` if page analysis not found
- Used by both Tool and API endpoint

**`get_page_analysis_id()`**:

**Purpose**: Retrieves only the page analysis ID (UUID) from the `page_analyses` table. Used to link chat messages to specific pages via `context_page_id`.

**Function Signature**:
```python
def get_page_analysis_id(
    course_material_id: str,
    page_number: int,
    user_id: str
) -> Optional[str]
```

**Key Features**:
- Query Supabase `page_analyses` table with filters
- Returns the `id` (UUID) of the page analysis record, or `None` if not found
- User authorization via RLS (Row Level Security)
- Used by chat endpoints to set `context_page_id` when persisting messages
- Returns `None` gracefully if page analysis doesn't exist yet (e.g., still processing)

**Dependencies**: 
- `get_supabase_client()` - Supabase client singleton

**Usage**: 
```python
from app.services.storage import get_page_analysis, get_page_analysis_id

analysis = get_page_analysis(course_material_id, page_number, user_id)
page_analysis_id = get_page_analysis_id(course_material_id, page_number, user_id)
```

**`get_course_material_summary()`**:

**Purpose**: Retrieves the overall summary of a course material from the `course_materials` table. The summary contains a JSON-encoded overview of the lecture topics, concepts, and key themes for the entire course material.

**Function Signature**:
```python
def get_course_material_summary(
    course_material_id: str,
    user_id: str
) -> Optional[dict]
```

**Key Features**:
- Query Supabase `course_materials` table with filters
- Retrieves the `summary` TEXT field
- Attempts to parse as JSON (returns parsed dict if valid JSON)
- Falls back to plain text format if not valid JSON
- Returns `None` if summary not found or empty
- User authorization via RLS (Row Level Security)
- Used by `GetCourseMaterialSummaryTool` to provide lecture overview context

**Related Files**: 
- `backend/app/tools/page_analysis_tool.py` - Tool that uses `get_page_analysis()`
- `backend/app/tools/course_material_tool.py` - Tool that uses `get_course_material_summary()`
- `backend/app/api/endpoints.py` - API endpoints that use these functions for message persistence

---

### `backend/app/api/endpoints.py` (Updated)

**New Endpoints**:

**`GET /api/page-analysis`**:
- Query params: `course_material_id`, `page_number`, `user_id`
- Returns: `PageAnalysisDataResponse` with analysis data
- Validates user exists
- Uses `get_page_analysis()` service function

**`POST /api/chat/initiate`**:
- **Langfuse Prompt Management**: Loads special prompts dynamically from Langfuse:
  - `tutor-agent/welcome-back`: For returning students with chat history
  - `tutor-agent/normal-greeting-after-welcome-back`: When welcome back was already sent
  - `tutor-agent/first-visit`: For first-time visitors
  - `tutor-agent/page-change-new-thread`: When navigating to new page without existing thread
  - `tutor-agent/page-change-existing-thread`: When navigating to new page with existing thread
- Prompts are compiled with variables (page_number, summary, completed_pages, total_pages, etc.)
- Helper function `get_tutor_prompt()` loads and compiles prompts from Langfuse
- Body: `ChatInitiateRequest` with `material_id`, `page_number`, `user_id`
- Returns: `StreamingResponse` with SSE events
- **Key Feature**: Injects system message for page change context
  - Message: `"SYSTEM EVENT: User navigated to Page {page_number}. Summary: {summary}. Please greet the user and explain the content."`
- Creates TutorAgent instance
- Thread ID: `material_id` (continuous conversation)
- Streams agent response as SSE

**`POST /api/chat/message`**:
- Body: `ChatMessageRequest` with `material_id`, `message`, `user_id`
- Returns: `StreamingResponse` with SSE events
- Continues conversation in existing thread (thread_id = material_id)
- Streams agent response as SSE

**Streaming Format**:
- Server-Sent Events (SSE)
- Chunks: `data: {"node": "agent", "messages": [...]}\n\n`
- End marker: `data: [DONE]\n\n`

**Dependencies**: 
- `app.agents.tutor` - TutorAgent
- `app.services.analyzer` - `get_gemini_model()` for LLM initialization
- `app.services.storage` - `get_page_analysis()` for page data
- `langgraph.checkpoint.memory` - MemorySaver for agent persistence
- `fastapi.responses` - StreamingResponse

**Related Files**: 
- `backend/app/agents/tutor/tutor_agent.py` - Agent implementation
- `backend/app/models/schemas.py` - Request/response schemas

---

### `backend/app/models/schemas.py` (Updated)

**New Schemas**:

**`ChatInitiateRequest`**:
- `material_id: str` - Course material ID
- `page_number: int` - Current page number (1-indexed)
- `user_id: str` - User ID

**`ChatMessageRequest`**:
- `material_id: str` - Course material ID
- `message: str` - User message content
- `user_id: str` - User ID

**`PageAnalysisQuery`**:
- `course_material_id: str` - Course material ID
- `page_number: int` - Page number (1-indexed)
- `user_id: str` - User ID

**`PageAnalysisDataResponse`**:
- `summary: str` - Page summary
- `key_terms: list[str]` - Key terms array
- `exam_questions: list[str]` - Exam questions array
- `diagram_description: Optional[str]` - Diagram description
- `raw_analysis: Optional[dict]` - Full JSON analysis

**Dependencies**: `pydantic` - BaseModel and Field

**Usage**: Used in API endpoints for request/response validation

---

### `frontend/lib/api/study.ts`

**Purpose**: API client functions for study session chat and page analysis.

**Key Functions**:

**`parseSSEChunk(chunk: string)`**:
- Parses SSE data chunks to extract message data
- Handles `[DONE]` marker
- Returns parsed JSON or null

**`initiateChat(...)`**:
- Initiates chat session for a study page
- Uses POST request with fetch and ReadableStream
- Processes SSE stream and calls `onChunk` callback
- Returns close function for cleanup
- Handles errors and completion

**`sendMessage(...)`**:
- Sends user message in existing chat session
- Uses POST request with fetch and ReadableStream
- Processes SSE stream and calls `onChunk` callback
- Returns Promise that resolves on completion

**`getPageAnalysis(...)`**:
- Fetches page analysis data from API
- Returns `PageAnalysisData` object
- Error handling with user-friendly messages

**Key Features**:
- SSE streaming support using ReadableStream API
- Error handling with callbacks
- Type-safe with TypeScript interfaces
- Environment variable for API URL

**Dependencies**: 
- `@/types` - ChatMessage, PageAnalysisData types
- Environment variable: `NEXT_PUBLIC_API_URL`

**Usage**: Imported in StudyReader component for chat functionality

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Uses these functions
- `frontend/types/index.ts` - Type definitions

---

### `frontend/components/study/pdf-viewer.tsx`

**Purpose**: Client Component for displaying a single PDF page using react-pdf.

**Key Components**:
- `react-pdf` `Document` and `Page` components
- PDF.js worker configuration (CDN)
- Loading and error states
- Responsive width calculation

**Key Features**:
- **SSR Disabled**: Must be dynamically imported with `ssr: false` (Canvas not available on server)
- Single page display (controlled by `pageNumber` prop)
- Loading state while PDF loads
- Error handling with user-friendly messages
- Responsive width (max 800px or 60% of viewport)

**Props**:
- `file: string | File` - PDF URL or File object
- `pageNumber: number` - Page to display (1-indexed)
- `onLoadError?: (error: Error) => void` - Error callback

**Dependencies**: 
- `react-pdf` - PDF rendering library
- PDF.js worker from CDN

**Usage**: Dynamically imported in StudyReader:
```tsx
const PdfViewer = dynamic(() => import('./pdf-viewer').then((mod) => ({ default: mod.PdfViewer })), {
  ssr: false,
})
```

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Uses this component
- `frontend/app/(dashboard)/dashboard/courses/[courseId]/study/[materialId]/page.tsx` - Study page

---

### `frontend/components/study/chat-interface.tsx`

**Purpose**: Client Component for chat interface using shadcn conversation and message components.

**Key Components**:
- `Conversation`, `ConversationContent` from shadcn
- `Message`, `MessageContent` from shadcn
- Input field with send button
- Loading and streaming indicators

**Key Features**:
- Message list display with role-based styling
- Auto-scroll to new messages (via Conversation component)
- Input field with form submission
- Loading state during agent response
- Streaming indicator
- Empty state when no messages

**Props**:
- `messages: ChatMessage[]` - Array of chat messages
- `onSend: (message: string) => void` - Callback for sending messages
- `isLoading: boolean` - Loading state
- `isStreaming?: boolean` - Streaming state

**Dependencies**: 
- `@/components/ai/conversation` - Conversation components
- `@/components/study/chat-message` - Individual message component
- `@/components/study/tutor-prompt-input` - Input component
- `@/types` - ChatMessage type

**Usage**: Used in StudyReader component

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Uses this component
- `frontend/components/study/chat-message.tsx` - Message rendering
- `frontend/components/study/tutor-prompt-input.tsx` - Input component

---

### `frontend/components/study/chat-message.tsx`

**Purpose**: Individual chat message component with modern bubble design and Markdown support.

**Key Features**:
- Avatar display (black circle with "H" for assistant, gray with user icon for user)
- Message bubbles with different styles for user (black) and assistant (gray)
- Full Markdown rendering with custom styling
- Responsive layout with proper spacing

**Props**:
- `id: string` - Message ID
- `role: "user" | "assistant"` - Message role
- `content: string` - Message content (Markdown supported)

**Design**:
- User messages: Black background (`bg-black text-white`), right-aligned
- Assistant messages: Gray background (`bg-gray-100 text-gray-900`), left-aligned
- Avatars: 8x8 rounded circles
- Message bubbles: `rounded-2xl px-4 py-3`

**Dependencies**: 
- `react-markdown` - Markdown rendering
- `lucide-react` - Icons (User icon)
- `@/lib/utils` - Utility functions (cn)

**Usage**: Used in ChatInterface component

**Related Files**: 
- `frontend/components/study/chat-interface.tsx` - Parent component

---

### `frontend/components/study/prompt-input.tsx`

**Purpose**: Reusable prompt input components for chat interfaces.

**Key Components**:
- `PromptInput` - Main form wrapper with rounded border
- `PromptInputTextarea` - Textarea with Enter key handling
- `PromptInputToolbar` - Toolbar container
- `PromptInputTools` - Left side tools container
- `PromptInputButton` - Toolbar button component
- `PromptInputSubmit` - Submit button with status icons

**Features**:
- Enter key submits (Shift+Enter for newline)
- Auto-resizing textarea
- Status-based icon display (ready/submitted/streaming/error)
- Tool buttons (Paperclip, Mic, etc.)

**Dependencies**: 
- `@/components/ui/button` - Button component
- `@/components/ui/textarea` - Textarea component
- `@/components/ui/loader` - Loader component
- `lucide-react` - Icons

**Usage**: Used in TutorPromptInput component

**Related Files**: 
- `frontend/components/study/tutor-prompt-input.tsx` - Concrete implementation

---

### `frontend/components/study/tutor-prompt-input.tsx`

**Purpose**: Concrete prompt input component for tutor chat with status indicators.

**Key Features**:
- Status bar showing agent status (green dots)
- PromptInput with textarea and toolbar
- Tool buttons (Paperclip, Mic/Voice)
- Submit button with status-based icons
- Optional context information display
- German placeholder text

**Props**:
- `onSubmit: (message: string) => void` - Submit handler
- `isLoading?: boolean` - Loading state
- `isStreaming?: boolean` - Streaming state
- `placeholder?: string` - Textarea placeholder
- `contextInfo?: string` - Context information to display

**Design**:
- Status indicators with green dots
- German text: "🧠 Tutor-Agent aktiv", "Lerntutor bereit"
- Placeholder: "Stellen Sie Fragen zu den Folien oder zum Lernstoff..."

**Dependencies**: 
- `@/components/study/prompt-input` - Base components
- `lucide-react` - Icons

**Usage**: Used in ChatInterface component

**Related Files**: 
- `frontend/components/study/chat-interface.tsx` - Parent component
- `frontend/components/study/prompt-input.tsx` - Base components

---

### `frontend/components/ui/loader.tsx`

**Purpose**: Reusable loading spinner component.

**Key Features**:
- Configurable size
- Smooth spinning animation
- SVG-based circular spinner

**Props**:
- `size?: number` - Size of the loader (default: 16)
- Standard HTML div props

**Usage**: Used in various components for loading states

**Related Files**: 
- `frontend/components/study/prompt-input.tsx` - Uses for submit button
- `frontend/components/study/task-list.tsx` - Uses for running tasks

---

### `frontend/components/study/task-list.tsx`

**Purpose**: Task list components for displaying step-by-step task progress.

**Key Components**:
- `Task` - Individual task item with status
- `TaskList` - Container for multiple tasks

**Task Status Types**:
- `pending` - Gray border/background
- `running` - Blue border/background with spinner
- `completed` - Green border/background with checkmark
- `error` - Red border/background with X icon

**Props**:
- `status: TaskStatus` - Task status
- `title: string` - Task title
- `description?: string` - Optional description
- `children?: React.ReactNode` - Optional additional content

**Design**:
- Status-based color coding
- Icons for each status (spinner, checkmark, X, empty circle)
- "läuft..." label for running tasks

**Dependencies**: 
- `@/components/ui/loader` - Loader component
- `lucide-react` - Icons (Check, X)

**Usage**: Optional component for displaying agent task progress

**Related Files**: 
- `frontend/components/ui/loader.tsx` - Uses loader for running state

---

### `frontend/components/study/study-reader.tsx`

**Purpose**: Main client component for study session with split-screen layout (PDF left, Chat right).

**Key Components**:
- `react-resizable-panels` for split-screen layout
- Dynamically imported `PdfViewer` (SSR disabled)
- `ChatInterface` for chat functionality
- Navigation arrows for page navigation
- Page counter display

**Key Features**:
- Split-screen layout with resizable panels (50/50 default)
- Page navigation with previous/next buttons
- Automatic chat initiation on page change with debouncing
- **Debouncing**: Waits 500ms after last page change before initiating chat
- **Request-ID-Tracking**: Only processes chunks from the latest request to prevent race conditions
- **Fast Scrolling Detection**: Skips chat initiation when user scrolls through more than 3 pages in 1 second
- SSE streaming for agent responses
- Message state management
- Cleanup on unmount

**State Management**:
- `currentPage: number` - Current page number (1-indexed)
- `messages: ChatMessage[]` - Chat message history
- `isLoading: boolean` - Loading state
- `isStreaming: boolean` - Streaming state
- `showTools: boolean` - Tool visibility toggle (persisted in localStorage)
- `toolCallsByMessage: Map<string, ToolCall[]>` - Tool calls per message

**Refs for Debouncing and Request Tracking**:
- `debounceTimerRef`: Timer for debouncing page changes
- `currentRequestIdRef`: Current request ID to filter outdated chunks
- `pageChangeHistoryRef`: History of recent page changes for fast scrolling detection

**Event Handlers**:
- `handlePageChange(newPage, skipStateUpdate?, isInitialOpen?)`: 
  - Debounced page change handler (500ms delay)
  - Detects fast scrolling (>3 pages in 1 second) and skips chat initiation
  - Generates unique request ID for each chat initiation
  - Only initiates chat if user stops scrolling
- `initiateChatForPage(page, requestId, isInitialOpen?)`: 
  - Internal function that actually starts the chat
  - Filters chunks by request ID to ignore outdated responses
  - Handles all chunk types (errors, tool calls, tool responses, deltas, messages)
- `handleSendMessage(message)`: Sends user message
- `handlePreviousPage()`, `handleNextPage()`: Page navigation

**Race Condition Prevention**:
- **Debouncing**: Prevents multiple simultaneous requests when user scrolls quickly
- **Request-ID-Tracking**: Each chat request gets a unique ID; only chunks matching the current request ID are processed
- **Fast Scrolling Detection**: When user scrolls through >3 pages in 1 second, chat initiation is skipped entirely
- All chunk handlers check `currentRequestIdRef.current === requestId` before processing

**useEffect Hooks**:
- On mount: Loads study session and initiates chat for saved/last page
- On `currentPage` change: Debounced chat initiation for new page
- On unmount: Cleans up stream connections and debounce timers

**Dependencies**: 
- `react-resizable-panels` - Split-screen layout
- `next/dynamic` - Dynamic import for PDF viewer
- `@/components/study/pdf-viewer` - PDF display
- `@/components/study/chat-interface` - Chat interface
- `@/lib/api/study` - API client functions
- `@/types` - ChatMessage type

**Usage**: Used in study page route

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/[courseId]/study/[materialId]/page.tsx` - Study page

---

### `frontend/app/(dashboard)/dashboard/courses/[courseId]/study/[materialId]/page.tsx`

**Purpose**: Server Component page for study session with PDF viewer and chat.

**Key Components**:
- Server-side authentication and authorization
- Course material data fetching
- Supabase Storage signed URL generation for PDF
- StudyReader component integration
- Sidebar layout consistent with dashboard

**Key Features**:
- Server Component for secure data fetching
- Validates course material belongs to user
- Generates signed URL for PDF (1 hour expiry)
- 404 handling if material not found
- Error handling for PDF URL generation

**Route Parameters**:
- `courseId: string` - Course ID
- `materialId: string` - Course material ID

**Data Fetching**:
1. Validates user authentication
2. Fetches course material from Supabase
3. Validates material belongs to user and course
4. Generates signed URL for PDF from Supabase Storage
5. Passes data to StudyReader component

**Dependencies**: 
- `@/lib/auth` - Authentication utilities (requireAuth)
- `@/lib/supabase/server` - Server-side Supabase client
- `@/components/dashboard/sidebar` - Dashboard sidebar
- `@/components/study/study-reader` - Study reader component
- `@/components/ui/sidebar` - SidebarProvider and SidebarInset
- `next/navigation` - notFound() for 404 handling

**Usage**: Accessible at `/dashboard/courses/[courseId]/study/[materialId]` route

**User Flow**:
1. User navigates to study page (e.g., from course detail page)
2. Server validates authentication and material ownership
3. Generates signed URL for PDF
4. Renders StudyReader with PDF and chat interface
5. User can navigate pages and chat with tutor agent

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Main study component
- `frontend/app/(dashboard)/dashboard/courses/[id]/page.tsx` - Course detail page (navigation source)
- `frontend/components/study/no-page-scroll.tsx` - Prevents page scrolling on StudyReader page

---

### `frontend/components/study/no-page-scroll.tsx`

**Purpose**: Client component that prevents page-level scrolling by adding a CSS class to html/body elements. Used only on the StudyReader page to prevent unwanted page scrolling while allowing internal component scrolling.

**Key Features**:
- Adds `no-page-scroll` class to `document.documentElement` (html) and `document.body` on mount
- Removes the class on unmount to restore normal scrolling behavior
- Uses `useEffect` hook for lifecycle management
- Returns `null` (no visual output)

**How it works**:
1. On component mount, adds `no-page-scroll` class to html and body
2. CSS rule `html.no-page-scroll, body.no-page-scroll` applies `height: 100%` and `overflow: hidden`
3. On component unmount, removes the class to restore normal scrolling

**Usage**: 
- Import and use as a component on pages where page-level scrolling should be disabled
- Currently used only on the StudyReader page (`/dashboard/courses/[id]/study/[materialId]`)

**Dependencies**: 
- React hooks (`useEffect`)
- CSS class defined in `globals.css`

**Related Files**: 
- `frontend/app/(dashboard)/dashboard/courses/[id]/study/[materialId]/page.tsx` - Uses this component
- `frontend/app/globals.css` - Defines `.no-page-scroll` CSS class

---

## Test Scripts

### `backend/test_tutor_agent.py`

**Purpose**: Interactive test script for testing the TutorAgent with continuous conversation support, independent of the frontend.

**Key Components**:
- **Initialization**: Sets up LLM (via `get_gemini_model()`), MemorySaver checkpointer, and TutorAgent with German language configuration
- **Interactive REPL Loop**: Continuous conversation interface with command support
- **State Management**: Manages and displays `material_id`, `user_id`, `current_page`, and `thread_id` for testing
- **Command Interface**: Special commands for testing:
  - `!page <number>` - Set current page number
  - `!material <id>` - Set material ID
  - `!user <id>` - Set user ID
  - `!history` - Show full conversation history with message types
  - `!clear` - Clear conversation and start new thread
  - `!help` - Show help message
  - `!quit` - Exit script
- **State Injection**: Properly passes `TutorState` fields (`current_page`, `material_id`, `user_id`) to agent graph for tool calls
- **Error Handling**: Comprehensive error handling with helpful messages for API key, database, and general errors
- **Output Formatting**: User-friendly output with state information, formatted agent responses, and conversation history display

**Key Functions**:
- `print_banner()`: Displays welcome message and available commands
- `print_state_info()`: Shows current state values (material_id, user_id, current_page, thread_id)
- `show_history()`: Displays conversation history with message type indicators
- `run_agent()`: Executes agent with proper state injection, handles new vs existing threads, extracts AI response from result
- `main()`: Main interactive loop with command parsing and error handling

**Usage**:
```bash
cd backend
python test_tutor_agent.py
# Or with debug mode:
python test_tutor_agent.py --debug
```

**Dependencies**:
- `app.agents.tutor.TutorAgent`
- `app.services.analyzer.get_gemini_model`
- `langgraph.checkpoint.memory.MemorySaver`
- `langchain_core.messages` (HumanMessage, SystemMessage, AIMessage, ToolMessage)

**Testing Scenarios**:
1. Simple conversation: User asks questions, agent responds
2. Tool usage: Agent calls `get_page_analysis` tool with automatic state injection
3. State updates: Change page/material/user during conversation
4. Conversation persistence: Agent remembers previous messages via thread_id
5. Error handling: Test with invalid API keys, database errors, etc.

**Related Files**:
- `backend/app/agents/tutor/tutor_agent.py` - The agent being tested
- `backend/app/tools/page_analysis_tool.py` - Tool used by agent
- `backend/app/services/analyzer.py` - LLM initialization

---

### `backend/app/services/session_storage.py`

**Purpose**: Helper module for persisting study session conversations and chat messages in Supabase.

**Key Components**:
- `get_or_create_study_conversation(user_id, course_material_id, course_id?, initial_page?)`:
  - Finds or creates a row in `conversations` with `session_type = 'study'` and `metadata.course_material_id`.
  - Stores `last_page_number` in `metadata` when provided.
- `update_conversation_progress(conversation_id, last_page_number)`:
  - Safely patches the `metadata` JSONB of a conversation to update the last visited page.
- `append_messages(conversation_id, messages_with_roles)`:
  - Inserts chat messages into `messages` with `role`, `content`, and optional `context_page_id`.
  - Skips invalid entries to avoid breaking chat flow.
- `load_conversation_with_messages(user_id, course_material_id, limit=50)`:
  - Loads the study conversation and up to `limit` most recent messages (oldest-first) for a user and material.

**Database Tables Used**:
- `conversations`: Study sessions with `session_type = 'study'` and metadata (course_material_id, last_page_number).
- `messages`: Individual chat messages linked via `conversation_id`.

**Usage**:
```python
from app.services.session_storage import (
    get_or_create_study_conversation,
    update_conversation_progress,
    append_messages,
    load_conversation_with_messages,
)
```

---

### `backend/app/api/endpoints.py` (Study Session Persistence Updates)

**Purpose**: Extend existing chat endpoints to persist tutor conversations and study progress in Supabase and expose a session-loading endpoint for the frontend.

**New/Updated Behaviors**:
- `/api/chat/initiate`:
  - Looks up `course_material_id` and `course_id` from `course_materials`.
  - Uses `get_or_create_study_conversation` to bind a Supabase `conversation` to `(user_id, course_material_id)`.
  - Uses `conversation.id` as `thread_id` for LangGraph `MemorySaver`.
  - Streams the tutor greeting for the current page and buffers assistant chunks.
  - After streaming, persists:
    - a combined `assistant` response with `context_page_id` set to the `page_analyses.id` for the current page,
    - and updates `last_page_number` in `conversations.metadata`.
  - The `context_page_id` links each message to the specific page analysis, allowing later queries to filter messages by page.
  - Optionally bootstraps LangGraph state from recent Supabase messages if the in-memory graph has no history (e.g., after backend restart).
- `/api/chat/message`:
  - Resolves the same study `conversation` for `(user_id, material_id)` and uses its `id` as `thread_id`.
  - Reads `current_page` from LangGraph state, falling back to `conversations.metadata.last_page_number` when necessary.
  - Streams the tutor reply, buffers assistant chunks, and persists:
    - the `user` message with `context_page_id` set to the `page_analyses.id` for the current page,
    - the combined `assistant` response with the same `context_page_id`,
    - and updated `last_page_number` if known.
  - Both user and assistant messages are linked to the page via `context_page_id` for proper context tracking.
- `/api/study/session` (new):
  - Query params: `material_id`, `user_id`, optional `limit`.
  - Validates user and ownership of `course_materials` record.
  - Uses `load_conversation_with_messages` to load the study conversation and recent messages.
  - Determines `lastPage` from `metadata.last_page_number` (bounded by `page_count`), defaults to 1.
  - Returns shape:
    - `{ "lastPage": number, "messages": [{ id, role, content, timestamp }] }`
  - Used by the frontend to restore page position and chat history when reopening the Study Reader.

**Related Files**:
- `backend/app/services/session_storage.py` - Supabase helpers for conversations and messages.
- `frontend/lib/api/study.ts` - Client functions including `getStudySession`.
- `frontend/components/study/study-reader.tsx` - Uses session data to restore state on mount.

---

### `frontend/components/ui/switch.tsx`

**Purpose**: Radix UI Switch component for toggling binary settings in the UI.

**Key Components**:
- `Switch`: Main switch component built on `@radix-ui/react-switch`
- Styled with Tailwind CSS for consistent design
- Supports keyboard interaction and accessibility

**Key Features**:
- Binary toggle state (checked/unchecked)
- Accessible with keyboard support
- Customizable styling via className prop
- Smooth transitions

**Dependencies**: 
- `@radix-ui/react-switch` - Radix UI primitive
- `@/lib/utils` - `cn` utility for className merging

**Usage**: Used in ChatInterface for toggling tool visibility

**Related Files**: 
- `frontend/components/study/chat-interface.tsx` - Uses Switch for tool visibility toggle

---

### `frontend/components/ui/tool.tsx`

**Purpose**: Tool display component for showing AI agent tool calls in the chat interface. Based on shadcn Tool component, adapted for our ToolCall data structure.

**Key Components**:
- `Tool`: Main collapsible component for displaying tool information
- `ToolCall` interface: Defines tool call structure (id, name, args, state)
- Status badges: Visual indicators for tool state (pending, running, completed, error)
- Collapsible sections: Expandable details for tool parameters

**Key Features**:
- Collapsible display with tool name and status
- JSON parameter display with syntax highlighting
- Status badges with icons (pending, running, completed, error)
- Dezente Integration in chat messages
- **Timeout Management**: 1-minute timeout with visual feedback
- **Waiting State**: Shows spinner and "Warte auf Antwort" message while waiting for response
- **Auto-State Detection**: Automatically shows "running" state when no result is present, only shows "completed" when result is available

**State Management**:
- `isOpen`: Controls collapsible state
- `hasTimedOut`: Tracks if 1-minute timeout has been reached
- Tool state: `pending` | `running` | `completed` | `error`
- **State Logic**: If no result is present, state is automatically set to "running" (waiting for response). Only shows "completed" when result is available.

**Timeout Behavior**:
- 1-minute (60 seconds) timeout timer starts when tool call is created without result
- Shows spinner and "Warte auf Antwort" message during waiting period
- After timeout, shows timeout message but continues waiting for response
- Timer is cleared when result arrives

**Dependencies**: 
- `lucide-react` - Icons (WrenchIcon, CheckCircleIcon, etc.)
- `@/components/ui/badge` - Status badges
- `@/components/ui/collapsible` - Collapsible container
- `@/components/ui/loader` - Spinner component for waiting state
- `@/lib/utils` - Utility functions

**Usage**: Displayed in ChatMessage component when `showTools` is enabled and `toolCalls` are present

**Related Files**: 
- `frontend/components/study/chat-message.tsx` - Uses Tool component to display tool calls
- `frontend/types/index.ts` - Defines ToolCall interface

---

### `frontend/types/index.ts` (ToolCall Extension)

**Purpose**: TypeScript type definitions extended with ToolCall interface and ChatMessage.toolCalls field.

**New Types**:
- `ToolCall`: Interface for tool call information
  - `id: string` - Unique tool call identifier
  - `name: string` - Tool name (e.g., "get_page_analysis")
  - `args: Record<string, any>` - Tool arguments/parameters
  - `state?: 'pending' | 'running' | 'completed' | 'error'` - Optional tool execution state

**Extended Types**:
- `ChatMessage.toolCalls?: ToolCall[]` - Optional array of tool calls associated with a message

**Usage**: Used throughout the frontend to type tool call data from backend SSE streams

**Related Files**: 
- `frontend/components/ui/tool.tsx` - Uses ToolCall interface
- `frontend/components/study/study-reader.tsx` - Manages tool calls in state
- `frontend/lib/api/study.ts` - Parses tool calls from SSE stream

---

### `backend/app/api/endpoints.py` (Tool Extraction)

**Purpose**: Backend API endpoints extended to extract and stream tool call information from LangGraph agent responses.

**Key Changes**:
- **Tool Extraction**: In both `initiate_chat` and `send_chat_message` functions:
  - Detects `AIMessage.tool_calls` attribute
  - Extracts tool call information (id, name, args)
  - Serializes tool calls to JSON
  - Sends tool call events via SSE stream before assistant message

**Tool Event Format**:
```python
{
  "type": "tool_call",
  "tool_calls": [
    {
      "id": "...",
      "name": "get_page_analysis",
      "args": {...}
    }
  ],
  "message_id": "..."
}
```

**Streaming**:
- Tool events sent as separate SSE events
- Tool events precede the final assistant message
- Tool information extracted from LangChain `AIMessage.tool_calls`

**Dependencies**: 
- `langchain_core.messages.AIMessage` - Message type with tool_calls attribute
- JSON serialization for tool call data

**Usage**: Frontend receives tool call events via SSE and displays them in chat interface

**Related Files**: 
- `frontend/lib/api/study.ts` - Parses tool call events
- `frontend/components/study/study-reader.tsx` - Handles tool call events

---

### `frontend/components/study/chat-interface.tsx` (Switch Integration)

**Purpose**: Chat interface component extended with tool visibility toggle switch.

**Key Changes**:
- **New Props**:
  - `showTools?: boolean` - Controls tool visibility
  - `onToggleTools?: (enabled: boolean) => void` - Callback for toggle changes
- **Switch Component**: 
  - Positioned dezent oben rechts im Chat-Header
  - Label: "Tools anzeigen"
  - Persists state via localStorage (handled in parent)

**Features**:
- Dezente Switch-Position (oben rechts)
- Label für bessere UX
- State wird an ChatMessage weitergegeben

**Dependencies**: 
- `@/components/ui/switch` - Switch component
- `@/components/ui/label` - Label component

**Usage**: User can toggle tool visibility for development/debugging purposes

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Manages showTools state and localStorage
- `frontend/components/study/chat-message.tsx` - Receives showTools prop

---

### `frontend/components/study/chat-message.tsx` (Tool Display)

**Purpose**: Chat message component extended to display tool calls when enabled.

**Key Changes**:
- **New Props**:
  - `toolCalls?: ToolCall[]` - Array of tool calls to display
  - `showTools?: boolean` - Controls whether tools are displayed
- **Tool Display**:
  - Tools shown above message content (dezent)
  - Only displayed for assistant messages
  - Only shown when `showTools === true` and `toolCalls` exist
  - Each tool displayed using `Tool` component

**Features**:
- Dezente Position (zwischen Avatar und Message-Content)
- Conditional rendering based on showTools flag
- Multiple tools displayed in sequence

**Dependencies**: 
- `@/components/ui/tool` - Tool display component
- `@/types` - ToolCall type

**Usage**: Shows which tools the agent used when generating a response

**Related Files**: 
- `frontend/components/ui/tool.tsx` - Tool display component
- `frontend/components/study/chat-interface.tsx` - Passes showTools prop

---

### `frontend/components/study/study-reader.tsx` (Tool State Management)

**Purpose**: Study reader component extended with tool call state management and localStorage persistence.

**Key Changes**:
- **New State**:
  - `showTools: boolean` - Loaded from localStorage on mount
  - `toolCallsByMessage: Map<string, ToolCall[]>` - Maps message IDs to tool calls
- **Tool Event Handling**:
  - Handles `tool_call` events from SSE stream
  - Associates tool calls with streaming messages
  - Updates messages with tool call information
- **localStorage Persistence**:
  - Key: `study-reader-show-tools`
  - Persists switch state across page reloads
  - Loads on component mount

**Features**:
- Tool calls tracked per message
- State persists across reloads
- Tool events handled in both `handlePageChange` and `handleSendMessage`

**Dependencies**: 
- `@/types` - ToolCall type
- `localStorage` - Browser storage API

**Usage**: Manages tool call state and provides toggle functionality to ChatInterface

**Related Files**: 
- `frontend/components/study/chat-interface.tsx` - Receives showTools state
- `frontend/lib/api/study.ts` - Provides tool call events

---

### `frontend/lib/api/study.ts` (Tool Event Parsing)

**Purpose**: API client functions extended to parse and handle tool call events from SSE stream.

**Key Changes**:
- **parseSSEChunk**: Extended return type to include tool call fields
  - `tool_calls?: ToolCall[]`
  - `message_id?: string`
- **Callback Signatures**: Updated `initiateChat` and `sendMessage` callbacks to accept tool call events
- **Event Handling**: Tool call events passed through to component handlers

**Features**:
- Tool events parsed from SSE stream
- Type-safe tool call data
- Backward compatible with existing message events

**Dependencies**: 
- `@/types` - ToolCall type

**Usage**: Parses tool call events from backend SSE stream and forwards to component handlers

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Handles parsed tool events
- `backend/app/api/endpoints.py` - Sends tool call events

---

## Flashcard Generation System

### `backend/app/agents/flashcards/flashcard_agent.py`

**Purpose**: Agent for generating Anki-compatible flashcards from lecture materials and conversation history.

**Key Components**:
- **FlashcardGeneratorAgent Class**: 
  - Processes page analyses and conversation messages to create educational flashcards
  - Uses LLM with structured output (Pydantic models) for page filtering and card generation
  - Skips intro/title/table of contents pages automatically
  - Generates 1-4 cards per page based on content complexity and conversation issues
  - **Langfuse Prompt Management**: Loads prompts dynamically from Langfuse with fallback to hardcoded versions
- **Methods**:
  - `_get_skip_decision_prompt()`: Loads skip-decision prompt from Langfuse or uses fallback
  - `_get_card_generation_prompt()`: Loads card-generation prompt from Langfuse or uses fallback
  - `_should_skip_page()`: Determines if a page should be skipped using LLM decision
  - `_generate_cards_for_page()`: Generates flashcards for a single page with conversation context
  - `generate_flashcards()`: Main entry point that processes all pages and returns card list
- **LLM Integration**: Uses Gemini model with structured output for consistent JSON responses
- **Conversation Context**: Analyzes user questions and assistant responses to identify understanding problems
- **Prompt Management**: 
  - Prompts are managed in Langfuse under `flashcard-agent/skip-decision` and `flashcard-agent/card-generation`
  - Prompts use variables ({{summary}}, {{key_terms}}, etc.) that are compiled at runtime
  - Automatic fallback to hardcoded prompts if Langfuse is unavailable or prompts cannot be loaded
  - Prompts can be updated in Langfuse UI without code changes

**Dependencies**: 
- `app.models.schemas` - PageSkipDecision, FlashcardGenerationResult, Flashcard models
- `app.services.storage` - get_all_page_analyses_for_material, get_messages_for_page
- `app.services.analyzer` - get_gemini_model
- `app.services.observability` - get_langfuse_client (for prompt management)

**Usage**: 
```python
from app.agents.flashcards import FlashcardGeneratorAgent

agent = FlashcardGeneratorAgent()
cards = agent.generate_flashcards(
    course_material_id="...",
    user_id="...",
    course_id="...",
    save_to_db=False
)
```

**Related Files**: 
- `backend/app/services/flashcard_service.py` - CSV export functionality
- `backend/app/api/endpoints.py` - Flashcard export endpoint
- `frontend/components/study/congratulations-screen.tsx` - UI for flashcard download

---

### `backend/app/services/flashcard_service.py`

**Purpose**: Service functions for flashcard operations, including CSV export for Anki import.

**Key Components**:
- **build_anki_csv()**: 
  - Converts flashcard list to Anki-compatible CSV format
  - Format: 3 columns (front, back, tags) separated by pipe (`|`) delimiter
  - Tags are space-separated strings
  - UTF-8 encoding with BOM for Excel compatibility
  - Proper CSV escaping for special characters and newlines

**Dependencies**: 
- Python `csv` and `io` modules

**Usage**: 
```python
from app.services.flashcard_service import build_anki_csv

csv_bytes = build_anki_csv(cards)
# Returns bytes ready for HTTP response
```

**Related Files**: 
- `backend/app/agents/flashcards/flashcard_agent.py` - Generates cards
- `backend/app/api/endpoints.py` - Uses this for CSV export

---

### `backend/app/services/storage.py` (Flashcard Functions)

**Purpose**: Extended with functions for flashcard generation support and retrieval.

**New Functions**:
- **get_messages_for_page()**: 
  - Retrieves all messages associated with a specific page analysis
  - Filters by `context_page_id` and validates user ownership via conversations
  - Returns messages ordered chronologically (oldest first)
- **save_flashcards()**: 
  - Batch inserts flashcards into the `flashcards` table
  - Links cards to source page analyses via `source_page_analysis_id`
  - Handles tag conversion (list to space-separated string)
  - Used automatically during flashcard generation to persist cards in Supabase
- **get_flashcards_for_material()**: 
  - Retrieves all flashcards for a course material from Supabase
  - Finds flashcards by querying page analyses for the material and then fetching linked flashcards
  - Returns list of flashcard dicts with: id, front, back, source_page_analysis_id, created_at, course_id, user_id
  - Enables downloading flashcards at any time without needing the original task

**Updated Functions**:
- **get_all_page_analyses_for_material()**: 
  - Now returns `id` field in addition to page_number, summary, key_terms, etc.
  - Required for linking messages to pages via `context_page_id`

**Dependencies**: 
- Supabase client (via `get_supabase_client()`)

**Usage**: 
```python
from app.services.storage import get_messages_for_page, save_flashcards, get_flashcards_for_material

messages = get_messages_for_page(page_analysis_id, user_id)
save_flashcards(cards, user_id, course_id)
flashcards = get_flashcards_for_material(course_material_id, user_id)
```

**Related Files**: 
- `backend/app/agents/flashcards/flashcard_agent.py` - Uses these functions
- `backend/app/services/flashcard_task_service.py` - Automatically saves flashcards to DB
- `backend/app/api/endpoints.py` - Uses get_flashcards_for_material for retrieval endpoints
- `backend/supabase/migrations/20260110111927_initial_schema.sql` - Database schema

---

### `backend/app/api/endpoints.py` (Flashcard Generation Endpoints)

**Purpose**: Background task-based flashcard generation with progress tracking and database persistence.

**New Endpoints**:
- **POST `/api/flashcards/generate`**:
  - Query parameters: `course_material_id`, `user_id`
  - Validates user and material ownership
  - Creates background task for flashcard generation
  - **Automatically saves flashcards to Supabase** after generation
  - Returns immediately with `task_id` (HTTP 202)
  - Response: `FlashcardTaskResponse` with task_id and status

- **GET `/api/flashcards/status/{task_id}`**:
  - Query parameters: `user_id` (for authorization)
  - Returns current task status and progress
  - Response: `FlashcardTaskStatusResponse` with progress (0.0-1.0), page counts, etc.

- **GET `/api/flashcards/download/{task_id}`**:
  - Query parameters: `user_id` (for authorization)
  - Downloads CSV file when task status is "completed"
  - Returns CSV file as StreamingResponse
  - Filename format: `flashcards_{course_title}_{material_name}.csv`
  - Note: Flashcards are also saved to Supabase, so they can be downloaded later via `/flashcards/download/{course_material_id}`

- **GET `/api/flashcards/{course_material_id}`**:
  - Query parameters: `user_id` (for authorization)
  - Retrieves all flashcards for a course material from Supabase
  - Returns JSON with flashcards list and count
  - Allows accessing flashcards at any time without needing the original task

- **GET `/api/flashcards/download/{course_material_id}`**:
  - Query parameters: `user_id` (for authorization)
  - Downloads flashcards directly from Supabase as CSV
  - Generates CSV on-the-fly from database
  - No task required - works anytime after flashcards have been generated
  - Filename format: `flashcards_{course_title}_{material_name}.csv`

- **POST `/api/flashcards/cancel/{task_id}`**:
  - Query parameters: `user_id` (for authorization)
  - Cancels a running task
  - Returns success status

**Key Features**:
- Non-blocking background processing (no more blocking the API)
- Real-time progress tracking (0.0 to 1.0)
- Async LLM calls with timeouts (30s skip decision, 60s card generation)
- **Automatic persistence to Supabase** - Flashcards are saved to database after generation
- **Database retrieval** - Flashcards can be accessed anytime via `/flashcards/{course_material_id}`
- **On-demand CSV download** - Download flashcards from database without needing the original task
- Proper error handling and task cancellation
- User authentication and authorization
- Filename sanitization for filesystem compatibility
- Support for multiple flashcards per page (via `source_page_analysis_id`)

**Dependencies**: 
- `app.services.flashcard_task_service` - Background task management (now saves flashcards to DB)
- `app.agents.flashcards` - FlashcardGeneratorAgent
- `app.services.flashcard_service` - build_anki_csv
- `app.services.storage` - Validation functions, save_flashcards, get_flashcards_for_material

**Usage**: 
```
# Start generation
POST /api/flashcards/generate?course_material_id=...&user_id=...
→ Returns: {"task_id": "...", "status": "pending", "message": "..."}

# Check progress
GET /api/flashcards/status/{task_id}?user_id=...
→ Returns: {"task_id": "...", "status": "running", "progress": 0.5, ...}

# Download when completed
GET /api/flashcards/download/{task_id}?user_id=...
→ Returns: CSV file

# Cancel if needed
POST /api/flashcards/cancel/{task_id}?user_id=...
→ Returns: {"success": true, "message": "Task cancelled"}
```

**Related Files**: 
- `backend/app/services/flashcard_task_service.py` - Task service implementation
- `frontend/lib/api/study.ts` - API client functions (needs update)
- `frontend/components/study/congratulations-screen.tsx` - UI component (needs update)

---

### `backend/app/models/schemas.py` (Flashcard Models)

**Purpose**: Extended with Pydantic models for flashcard generation.

**New Models**:
- **PageSkipDecision**: 
  - `skip: bool` - Whether to skip the page
  - `reason: str` - Brief reason for decision
  - Used for LLM structured output in page filtering
- **Flashcard**: 
  - `front: str` - Front side of card
  - `back: str` - Back side of card
  - `tags: list[str]` - Categorization tags
- **FlashcardGenerationResult**: 
  - `cards: list[Flashcard]` - List of generated cards
  - Used for LLM structured output in card generation

**Dependencies**: 
- `pydantic` - BaseModel, Field

**Usage**: 
```python
from app.models.schemas import PageSkipDecision, FlashcardGenerationResult

# Used with LLM structured output
llm.with_structured_output(PageSkipDecision)
llm.with_structured_output(FlashcardGenerationResult)
```

**Related Files**: 
- `backend/app/agents/flashcards/flashcard_agent.py` - Uses these models

---

### `backend/app/services/flashcard_task_service.py`

**Purpose**: Background task service for managing flashcard generation with progress tracking.

**Key Components**:
- **FlashcardTask**: Task model with status, progress, and metadata
  - Status enum: `pending`, `running`, `completed`, `failed`, `cancelled`
  - Progress tracking: 0.0 to 1.0
  - Page counts: total_pages, processed_pages
  - Error handling: error_message field
  - Result storage: csv_bytes, filename

- **FlashcardTaskService**: Singleton service managing tasks
  - `create_task()`: Creates new background task
  - `get_task()`: Retrieves task by ID
  - `cancel_task()`: Cancels running task
  - `_run_task()`: Background task execution
  - `_generate_flashcards_async()`: Async wrapper with timeouts

**Key Features**:
- In-memory task storage (can be replaced with Redis/DB in production)
- Async/await support for non-blocking execution
- Timeouts: 30s for skip decisions, 60s for card generation
- Progress updates during processing
- Error handling and cancellation support
- Thread-safe task management with asyncio.Lock

**Dependencies**: 
- `app.agents.flashcards` - FlashcardGeneratorAgent
- `app.services.flashcard_service` - build_anki_csv
- `app.services.storage` - Database functions
- `asyncio` - Async task management

**Usage**: 
```python
from app.services.flashcard_task_service import get_flashcard_task_service

task_service = get_flashcard_task_service()
task_id = await task_service.create_task(
    course_material_id="...",
    user_id="...",
    course_id="..."
)

task = await task_service.get_task(task_id)
print(f"Progress: {task.progress * 100}%")
```

**Production Considerations**:
- In-memory storage is lost on server restart
- For production, consider Redis or database-backed task storage
- Could be replaced with Celery, RQ, or cloud task services
- Task cleanup: Old completed tasks should be purged periodically

**Related Files**: 
- `backend/app/api/endpoints.py` - Uses this service for endpoints
- `backend/app/agents/flashcards/flashcard_agent.py` - Called by task service

---

### `frontend/components/study/congratulations-screen.tsx`

**Purpose**: Modal component shown after completing a lecture, offering flashcard download.

**Key Components**:
- **CongratulationsScreen Component**:
  - Displays success message and celebration UI
  - Provides "Flashcards runterladen" button
  - Handles CSV download with loading states
  - Shows success/error feedback via toast notifications
- **State Management**:
  - `isDownloading`: Loading state during generation
  - `downloadSuccess`: Success state after download
- **Download Flow**:
  - Calls `exportFlashcards()` API function
  - Creates blob download with proper filename
  - Handles errors gracefully with user feedback

**Dependencies**: 
- `@/lib/api/study` - exportFlashcards function
- `sonner` - Toast notifications
- `@/components/ui/card` - Card UI components
- `lucide-react` - Icons

**Usage**: 
```tsx
<CongratulationsScreen
  materialId={materialId}
  courseId={courseId}
  userId={userId}
  onClose={() => setShowCongratulations(false)}
/>
```

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Integrates this component
- `frontend/lib/api/study.ts` - Provides exportFlashcards function

---

### `frontend/lib/api/study.ts` (Flashcard Export Function)

**Purpose**: Extended with flashcard export API client function.

**New Function**:
- **exportFlashcards()**: 
  - Calls `/api/flashcards/export` endpoint
  - Returns Promise<Blob> for CSV file
  - Handles errors and HTTP status codes

**Dependencies**: 
- Fetch API
- Environment variable: `NEXT_PUBLIC_API_URL`

**Usage**: 
```typescript
import { exportFlashcards } from '@/lib/api/study'

const blob = await exportFlashcards(materialId, userId)
// Create download link from blob
```

**Related Files**: 
- `frontend/components/study/congratulations-screen.tsx` - Uses this function
- `backend/app/api/endpoints.py` - Provides the endpoint

---

### `frontend/components/study/study-reader.tsx` (Congratulations Integration)

**Purpose**: Extended with congratulations screen integration.

**Key Changes**:
- **New State**: `showCongratulations: boolean` - Controls visibility of congratulations screen
- **handleNextPage()**: 
  - Shows congratulations screen when user clicks "Next" on last page
  - Triggers when `currentPage === pageCount`
- **Rendering**: 
  - Conditionally renders `CongratulationsScreen` component
  - Overlay modal style with backdrop blur

**Features**:
- Automatic trigger when reaching last page
- Can be closed to return to lecture
- Integrated seamlessly with existing page navigation

**Dependencies**: 
- `@/components/study/congratulations-screen` - CongratulationsScreen component

**Usage**: User navigates through lecture, reaches last page, clicks "Next", sees congratulations screen with flashcard download option.

**Related Files**: 
- `frontend/components/study/congratulations-screen.tsx` - The modal component

---

### `backend/flashcard_prompt_test_dataset_langfuse.json`

**Purpose**: Dataset für Langfuse Prompt Testing des Flashcard Agents mit komplexen mathematischen Ausdrücken.

**Key Components**:
- **Dataset-Format**: Langfuse-kompatibles JSON-Format mit `input`-Objekten für jedes Dataset-Item
- **10 Testfälle**: Verschiedene mathematische Themen mit komplexen Formeln:
  - Lineare Algebra (Eigenwerte, Diagonalisierung)
  - Analysis (Gradient, Hesse-Matrix)
  - Differentialgleichungen (Matrixexponentialfunktion)
  - Funktionalanalysis (Banach-Räume, L^p-Normen)
  - Numerik (Newton-Verfahren, iterative Methoden)
  - Wahrscheinlichkeitstheorie (mehrdimensionale Verteilungen)
  - Topologie (metrische Räume)
  - Fourier-Analyse (Fourier-Transformation)
  - Optimierung (Lagrange-Multiplikatoren)
  - Komplexe Analysis (Residuensatz)
- **Input-Variablen**: Jedes Item enthält alle erforderlichen Variablen für den Flashcard Agent:
  - `summary`: Zusammenfassung mit mathematischen Formeln
  - `key_terms`: Liste von Fachbegriffen mit Notationen
  - `exam_questions`: Liste von Prüfungsfragen mit Berechnungen
  - `diagram_description`: Beschreibung mathematischer Visualisierungen
  - `conversation_context`: Beispielkonversationen mit Formeln
  - `course_id`, `material_id`, `page_number`: Metadaten
- **Metadata**: Jedes Item enthält zusätzliche Metadaten (Topic, Difficulty)

**Dependencies**: Wird vom Upload-Script `upload_langfuse_dataset.py` verwendet

**Usage**: 
```bash
# Dataset wird automatisch von upload_langfuse_dataset.py geladen
python backend/upload_langfuse_dataset.py
```

**Related Files**: 
- `backend/upload_langfuse_dataset.py` - Script zum Hochladen des Datasets
- `backend/app/agents/flashcards/flashcard_agent.py` - Verwendet die Variablen für Prompt-Generierung

---

### `backend/upload_langfuse_dataset.py`

**Purpose**: Python-Script zum Hochladen des Flashcard Agent Test-Datasets in Langfuse für Prompt Testing.

**Key Components**:
- **Dataset-Loading**: Lädt das JSON-Dataset aus `flashcard_prompt_test_dataset_langfuse.json`
- **Langfuse Integration**: 
  - Erstellt ein neues Dataset in Langfuse (oder verwendet existierendes)
  - Lädt alle Dataset-Items mit `input`-Objekten hoch
  - Validiert, dass jedes Item die erforderlichen Variablen enthält
- **Error Handling**: 
  - Prüft Langfuse Credentials (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
  - Validiert Dataset-Struktur
  - Zeigt Fortschritt beim Upload an
- **Unicode-Support**: Verwendet ASCII-kompatible Ausgaben für Windows-Kompatibilität

**Dependencies**: 
- `langfuse` - Langfuse Python SDK
- `python-dotenv` - Für .env Datei-Laden
- `flashcard_prompt_test_dataset_langfuse.json` - Das zu ladende Dataset

**Usage**: 
```bash
# Voraussetzungen: LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY in .env gesetzt
python backend/upload_langfuse_dataset.py
```

**Output**:
- Erstellt Dataset `flashcard-agent-math-expressions` in Langfuse
- Lädt 10 Testfälle mit komplexen mathematischen Ausdrücken hoch
- Gibt Anweisungen für nächste Schritte (Prompt Experiment erstellen)

**Wichtig für Langfuse Prompt Template**:
Das Prompt Template muss die folgenden Variablen verwenden:
- `{{summary}}`
- `{{key_terms}}` (wird als Liste übergeben, Code konvertiert zu String)
- `{{exam_questions}}` (wird als Liste übergeben, Code konvertiert zu String)
- `{{diagram_description}}`
- `{{conversation_context}}`
- `{{course_id}}`
- `{{material_id}}`
- `{{page_number}}` (wird als Integer übergeben, Code konvertiert zu String)

**Related Files**: 
- `backend/flashcard_prompt_test_dataset_langfuse.json` - Das hochgeladene Dataset
- `backend/app/agents/flashcards/flashcard_agent.py` - Verwendet die Variablen für Prompt-Generierung

---

### `backend/langfuse_to_anki_csv.py`

**Purpose**: Script zum direkten Konvertieren von Langfuse Trace-Exports in Anki-kompatible CSV-Dateien.

**Key Components**:
- **JSON-Parsing**: 
  - Liest Langfuse Trace-Export JSON-Dateien
  - Extrahiert JSON aus Markdown-Code-Blöcken (```json ... ```)
  - Unterstützt verschiedene Output-Formate (String, Dict, List)
- **Card-Extraktion**:
  - Findet alle Flashcard-Objekte in den Trace-Outputs
  - Validiert Cards (müssen 'front' und 'back' haben)
  - Normalisiert Tags (konvertiert zu Listen)
- **Anki CSV-Format**:
  - Verwendet Pipe-Delimiter (|) wie von Anki erwartet
  - UTF-8 mit BOM für Excel-Kompatibilität
  - Format: `front|back|tags`

**Dependencies**: 
- Standard Python-Bibliotheken: `json`, `csv`, `re`, `argparse`
- Keine externen Dependencies

**Usage**: 
```bash
# Basis-Verwendung
python backend/langfuse_to_anki_csv.py --input langfuse_export.json --output flashcards.csv

# Mit detaillierter Ausgabe
python backend/langfuse_to_anki_csv.py --input langfuse_export.json --output flashcards.csv --verbose
```

**Anki Import**:
1. Öffne Anki
2. File → Import
3. Wähle die CSV-Datei
4. **Wichtig**: Stelle sicher, dass "Fields separated by: Pipe (|)" ausgewählt ist
5. Klicke Import

**Output-Format**:
- CSV mit 3 Spalten: `front`, `back`, `tags`
- Tags sind space-separated
- Unterstützt mehrzeilige Inhalte
- UTF-8 Encoding mit BOM

**Related Files**: 
- `backend/app/services/flashcard_service.py` - Ähnliche CSV-Export-Funktionalität
- `backend/flashcard_prompt_test_dataset_langfuse.json` - Test-Dataset

---

## Frontend Math Rendering Files

### `frontend/components/study/chat-message.tsx` (KaTeX Integration)

**Purpose**: Chat message component that displays user and assistant messages. Enhanced to render mathematical expressions using KaTeX via `remark-math` and `rehype-katex` plugins (OpenAI-style approach).

**Key Changes**:
- **Math Rendering**: 
  - Uses `remark-math` plugin to recognize math expressions in Markdown
  - Uses `rehype-katex` plugin to render math with KaTeX
  - Follows OpenAI's approach: Markdown is parsed first, then math is recognized and rendered
- **Rendering Logic**:
  - Single `ReactMarkdown` component with both plugins
  - Inline math: `$formula$` (e.g., `$x^2 + y^2$`)
  - Display math: `$$formula$$` (e.g., `$$\int_0^1 f(x) dx$$`)
  - All Markdown features (bold, lists, code, etc.) work seamlessly with math
- **Styling**: Math expressions inherit text color from the message role (assistant/user)

**Dependencies**: 
- `react-markdown` - For Markdown rendering
- `remark-math` - For recognizing math expressions in Markdown
- `rehype-katex` - For rendering math with KaTeX
- `katex` - KaTeX library (CSS imported in `layout.tsx`)

**Usage**:
The component automatically renders math when the content contains:
- Inline math: `Das ist $x^2 + y^2$ eine Formel`
- Display math: `$$\int_0^1 f(x) dx$$`

**Related Files**: 
- `frontend/app/layout.tsx` - Imports KaTeX CSS
- `frontend/app/globals.css` - KaTeX styling rules
- `frontend/components/study/chat-interface.tsx` - Chat interface container

---

### `frontend/app/layout.tsx` (KaTeX CSS Import)

**Purpose**: Root layout component that imports KaTeX CSS for math rendering.

**Key Changes**:
- **KaTeX CSS Import**: 
  - Imports `katex/dist/katex.min.css` to enable proper math styling
  - Required for KaTeX to render correctly

**Dependencies**: 
- `katex` - KaTeX library

**Related Files**: 
- `frontend/components/study/chat-message.tsx` - Uses KaTeX for rendering

---

### `frontend/app/globals.css` (KaTeX Styling)

**Purpose**: Global CSS file that includes styling rules for KaTeX-rendered mathematical expressions to ensure proper integration with the chat interface design.

**Key Components**:
- **KaTeX Styling**:
  - Ensures KaTeX expressions inherit text color from parent
  - Display math: Proper vertical spacing (1em margin)

**Dependencies**: None (pure CSS)

**Related Files**: 
- All components using KaTeX rendering benefit from these styles

---

## Quiz Feature Files

### `backend/app/models/schemas.py` (Quiz Models)

**Purpose**: Pydantic models for quiz data structures and API request/response validation.

**Key Components**:
- **QuizQuestion**: Model for a single quiz question with id, question, options (Dict[str, str]), correct_answer (Literal["A","B","C","D"]), difficulty (Literal["easy","medium","hard"]), explanation
- **QuizData**: Model for complete quiz data structure with topic, questions (List[QuizQuestion]), metadata (Dict[str, int])
- **QuizCreate**: Input model for creating a quiz (start_page, end_page, course_material_id, user_id)
- **QuizSubmit**: Input model for submitting quiz answers (quiz_id, answers, user_id)
- **QuestionResult**: Model for individual question result (question_id, user_answer, correct_answer, correct, explanation)
- **QuizResult**: Response model for quiz submission results (quiz_id, score, correct_count, total_questions, question_results, completed_at, tutor_feedback)
- **QuizResponse**: Response model for quiz data retrieval (full quiz data with id, course_material_id, etc.)

**Dependencies**: 
- `pydantic` - For data validation
- `typing` - For type hints (Literal, Dict, List, Optional)

**Usage**: Used by API endpoints and services for request/response validation and data serialization.

**Related Files**: 
- `backend/app/api/endpoints.py` - Uses these models for API endpoints
- `backend/app/services/quiz_service.py` - Uses QuizData and QuizResult
- `backend/app/agents/quiz/quiz_generator_agent.py` - Uses QuizData for structured output

---

### `backend/app/services/storage.py` (get_page_analyses_for_range)

**Purpose**: Function to retrieve page analyses for a specific page range, used by QuizGeneratorAgent to get context for quiz generation.

**Key Function**:
- `get_page_analyses_for_range(course_material_id, user_id, start_page, end_page)`: Returns list of page analysis records for the specified page range

**Dependencies**: 
- `get_supabase_client()` - Supabase client for database queries

**Usage**: Called by QuizGeneratorAgent to fetch page analyses for quiz generation context.

**Related Files**: 
- `backend/app/agents/quiz/quiz_generator_agent.py` - Uses this function

---

### `backend/app/services/quiz_service.py`

**Purpose**: Business logic for quiz creation, retrieval, submission, and scoring.

**Key Functions**:
- `save_quiz()`: Save QuizData to `quizzes` table, return quiz_id
- `get_quiz()`: Retrieve quiz by ID with user authorization
- `calculate_score()`: Calculate score and generate QuestionResult list
- `submit_quiz_results()`: Save results to `quiz_results` table, prevent duplicates
- `get_quiz_result()`: Retrieve quiz result by ID

**Dependencies**: 
- `get_supabase_client()` - Supabase client for database operations
- `app.models.schemas` - QuizData, QuizResult, QuestionResult models

**Usage**: Called by API endpoints and tools for quiz management.

**Related Files**: 
- `backend/app/api/endpoints.py` - Uses these functions in quiz endpoints
- `backend/app/tools/quiz_tool.py` - Uses save_quiz()

---

### `backend/app/agents/quiz/quiz_generator_agent.py`

**Purpose**: Subagent that generates comprehension quizzes from lecture material. Used by the Tutor Agent when a subtopic is completed.

**Key Components**:
- Extends `BaseAgent` from `app.agents.base`
- Loads system prompt from Langfuse (`quiz-generator/system-prompt-de`)
- Uses `with_structured_output(QuizData)` for structured generation
- Implements `_parse_quiz_result()` method for robust Pydantic validation:
  - Handles QuizData instance (direct)
  - Handles dict (uses `QuizData.model_validate()`)
  - Handles string (extracts JSON from markdown, then validates)
- Validates difficulty distribution (1-2 easy, 1 medium, at least 1 hard)
- Langfuse tracing with user_id and session_id
- Error handling with detailed logging

**Key Methods**:
- `generate_quiz(start_page, end_page, course_material_id, user_id)`: Main entry point for quiz generation
- `_parse_quiz_result(result)`: Robust parsing with Pydantic validation
- `_validate_quiz(quiz_data)`: Validates quiz meets requirements

**Dependencies**: 
- `app.agents.base.BaseAgent` - Base agent class
- `app.models.schemas.QuizData` - Pydantic model for quiz structure
- `app.services.storage.get_page_analyses_for_range` - Fetch page analyses
- `app.services.observability` - Langfuse client and callback handler
- `app.services.analyzer.get_gemini_model` - LLM initialization

**Usage**: Called by CreateQuizTool when TutorAgent detects topic completion.

**Related Files**: 
- `backend/app/tools/quiz_tool.py` - Uses QuizGeneratorAgent
- `backend/app/agents/quiz/__init__.py` - Package initialization

---

### `backend/app/agents/quiz/__init__.py`

**Purpose**: Package initialization file for quiz agent subpackage.

**Key Components**:
- Exports `QuizGeneratorAgent` class

**Dependencies**: None

**Usage**: Allows importing QuizGeneratorAgent from `app.agents.quiz`

---

### `backend/app/tools/quiz_tool.py`

**Purpose**: Tool for creating quizzes from lecture material. Used by the Tutor Agent to generate quizzes when a subtopic is completed.

**Key Components**:
- `CreateQuizTool` class
- `_run()` method: Calls QuizGeneratorAgent, saves quiz, returns JSON string
- `to_langchain_tool()`: Converts to LangChain StructuredTool
- Input schema: `CreateQuizInput` with start_page, end_page, course_material_id, user_id

**Dependencies**: 
- `app.agents.quiz.QuizGeneratorAgent` - Subagent for quiz generation
- `app.services.quiz_service.save_quiz` - Save quiz to database
- `app.services.analyzer.get_gemini_model` - LLM initialization

**Usage**: Integrated into TutorAgent's tool list, automatically called when topic completion is detected.

**Related Files**: 
- `backend/app/agents/tutor/tutor_agent.py` - Uses CreateQuizTool

---

### `backend/app/agents/tutor/tutor_agent.py` (Quiz Integration)

**Purpose**: Tutor Agent with integrated quiz creation capability.

**Key Modifications**:
- Import `CreateQuizTool`
- Initialize `self.quiz_tool = CreateQuizTool()` in `__init__`
- Add to `self.langchain_tools` list
- Update `StateAwareToolNode.invoke()` and `ainvoke()` to inject `course_material_id` and `user_id` for `create_quiz` tool calls
- Update system prompt enhancement to mention automatic argument filling for `create_quiz`

**Dependencies**: 
- `app.tools.quiz_tool.CreateQuizTool` - Quiz creation tool

**Usage**: Automatically creates quizzes when detecting topic completion based on system prompt instructions.

**Related Files**: 
- `backend/app/tools/quiz_tool.py` - CreateQuizTool implementation

---

### `backend/app/api/endpoints.py` (Quiz Endpoints)

**Purpose**: API endpoints for quiz submission and retrieval, including tutor feedback generation.

**Key Endpoints**:
- `POST /api/quiz/submit`: Submit quiz answers
  - Validates user
  - Calls `submit_quiz_results()`
  - Generates tutor feedback using TutorAgent with Langfuse prompt (`tutor-agent/quiz-feedback-de`)
  - Returns `QuizResult` with `tutor_feedback` field
  
- `GET /api/quiz/{quiz_id}`: Get quiz data
  - Validates user authorization
  - Returns `QuizResponse` with full quiz data

**Key Features**:
- Tutor feedback generation after quiz submission:
  - Loads feedback prompt from Langfuse
  - Compiles prompt with quiz results (wrong/correct questions, score, etc.)
  - Calls TutorAgent to generate personalized feedback
  - Adds feedback to QuizResult response

**Dependencies**: 
- `app.services.quiz_service` - submit_quiz_results, get_quiz, get_quiz_result
- `app.models.schemas` - QuizSubmit, QuizResult, QuizResponse
- `app.agents.tutor.TutorAgent` - For feedback generation
- `app.services.session_storage.get_or_create_study_conversation` - For conversation context

**Usage**: Called by frontend when user completes a quiz.

**Related Files**: 
- `frontend/lib/api/study.ts` - submitQuiz API client function
- `frontend/components/study/quiz-component.tsx` - Calls submitQuiz

---

### `frontend/types/index.ts` (Quiz Types)

**Purpose**: TypeScript type definitions for quiz data structures matching backend Pydantic models.

**Key Interfaces**:
- `QuizQuestion`: id, question, options, correct_answer, difficulty, explanation
- `QuizData`: topic, questions, metadata
- `Quiz`: Full quiz with id, course_material_id, etc.
- `QuizAnswer`: question_id, answer
- `QuestionResult`: question_id, user_answer, correct_answer, correct, explanation
- `QuizResult`: quiz_id, score, correct_count, total_questions, question_results, completed_at, tutor_feedback
- Extended `ChatMessage` with optional `quiz` field

**Dependencies**: None (pure TypeScript types)

**Usage**: Import types in components: `import type { QuizQuestion, QuizResult } from '@/types'`

**Related Files**: 
- `frontend/components/study/quiz-component.tsx` - Uses QuizQuestion type
- `frontend/components/study/study-reader.tsx` - Uses QuizResult type
- `frontend/lib/api/study.ts` - Uses QuizResult type

---

### `frontend/lib/api/study.ts` (submitQuiz)

**Purpose**: API client function for quiz submission.

**Key Function**:
- `submitQuiz(quizId, answers, userId)`: POST to `/api/quiz/submit`, returns QuizResult

**Dependencies**: 
- `@/types` - QuizResult type

**Usage**: Called by QuizComponent when user completes all questions.

**Related Files**: 
- `frontend/components/study/quiz-component.tsx` - Calls submitQuiz
- `frontend/components/study/study-reader.tsx` - Uses submitQuiz in handleQuizComplete

---

### `frontend/components/study/quiz-component.tsx`

**Purpose**: React component for interactive quiz display in the chat interface.

**Key Features**:
- Step-by-step question display (one at a time)
- 4 answer buttons (A, B, C, D) with immediate feedback
- Progress bar showing completion percentage
- Score display after completion
- Submit button that calls `onComplete` callback
- Loading state during submission
- Visual feedback (green for correct, red for incorrect)
- Explanation display after each answer

**Key Props**:
- `quizId`: Quiz ID
- `topic`: Quiz topic name
- `questions`: Array of QuizQuestion objects
- `onComplete`: Callback function with user answers
- `isSubmitting`: Loading state during submission

**Dependencies**: 
- `@/components/ui/button` - Button component
- `@/components/ui/card` - Card components
- `@/components/ui/progress` - Progress bar
- `lucide-react` - Icons (CheckCircle2, XCircle, Loader2)
- `@/types` - QuizQuestion, QuizResult types

**Usage**: Rendered by ChatMessage component when a message contains quiz data.

**Related Files**: 
- `frontend/components/study/chat-message.tsx` - Renders QuizComponent
- `frontend/components/study/study-reader.tsx` - Provides quiz data and callbacks

---

### `frontend/components/study/chat-message.tsx` (Quiz Integration)

**Purpose**: Chat message component with quiz display support.

**Key Modifications**:
- Accept `quiz` prop (optional quiz data)
- Accept `onQuizComplete` callback prop
- Accept `isQuizSubmitting` prop for loading state
- Conditionally render `QuizComponent` if quiz exists and role is 'assistant'

**Dependencies**: 
- `@/components/study/quiz-component` - QuizComponent for quiz display

**Usage**: Automatically displays quiz when message contains quiz data.

**Related Files**: 
- `frontend/components/study/quiz-component.tsx` - Quiz display component
- `frontend/components/study/chat-interface.tsx` - Passes quiz props to ChatMessage

---

### `frontend/components/study/chat-interface.tsx` (Quiz Integration)

**Purpose**: Chat interface component with quiz handling support.

**Key Modifications**:
- Accept `onQuizComplete` callback prop
- Accept `submittingQuizId` prop for loading state
- Pass quiz props to ChatMessage components

**Dependencies**: 
- `@/components/study/chat-message` - ChatMessage component

**Usage**: Connects StudyReader quiz handling with ChatMessage components.

**Related Files**: 
- `frontend/components/study/study-reader.tsx` - Provides quiz callbacks
- `frontend/components/study/chat-message.tsx` - Receives quiz props

---

### `frontend/components/study/study-reader.tsx` (Quiz Integration)

**Purpose**: Main study reader component with quiz handling integration.

**Key Modifications**:
- Import `submitQuiz` from API client
- Add `submittingQuizId` state to manage loading state
- Handle `create_quiz` tool call response:
  - Extract `quiz_id` and `quiz_data` from tool result
  - Add quiz to ChatMessage state
- Implement `handleQuizComplete` callback:
  - Calls `submitQuiz` API
  - Adds result message with tutor feedback to chat
  - Manages loading state

**Key Features**:
- Extracts quiz data from tool call results (create_quiz tool)
- Manages quiz submission state
- Displays tutor feedback after quiz completion

**Dependencies**: 
- `@/lib/api/study.submitQuiz` - API client function
- `@/types` - ChatMessage, QuizResult types

**Usage**: Main component that orchestrates quiz creation, display, and submission.

**Related Files**: 
- `frontend/components/study/chat-interface.tsx` - Receives quiz callbacks
- `frontend/lib/api/study.ts` - submitQuiz function

---