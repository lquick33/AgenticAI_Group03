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
