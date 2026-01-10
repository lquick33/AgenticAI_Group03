# Supabase Migrations

This directory contains database migration files for the Lernkompanien project.

## Initial Schema Migration

**File**: `20260110111927_initial_schema.sql`

This migration sets up the complete database schema for the Lernkompanien learning platform, implementing the vision-first multimodal approach.

### What's Included

- **6 ENUMs**: learning_style, agent_persona, unit_status, file_status, sender_role, session_type
- **9 Tables**: profiles, user_preferences, courses, course_materials, page_analyses, learning_units, flashcards, conversations, messages
- **RLS Policies**: Complete Row Level Security for all tables
- **Triggers**: Automatic `updated_at` timestamp updates
- **Indexes**: Performance indexes for common queries
- **Storage**: Bucket and policies for course materials

### Key Features

- **Vision-First Multimodal Approach**: `page_analyses` table stores structured JSON from GPT-4o Vision analysis
- **User Isolation**: All tables have RLS policies ensuring users can only access their own data
- **Cascade Deletes**: Foreign keys configured with ON DELETE CASCADE for data integrity
- **Google Calendar Integration**: `learning_units` table supports bidirectional calendar sync

## Execution

### Option 1: Supabase Dashboard SQL Editor

1. Open your Supabase project dashboard
2. Navigate to SQL Editor
3. Copy the contents of `20260110111927_initial_schema.sql`
4. Paste and execute in the SQL Editor
5. Verify all objects were created successfully

### Option 2: Supabase CLI

```bash
# If using Supabase CLI locally
supabase db push

# Or link to remote project
supabase link --project-ref your-project-ref
supabase db push
```

## Verification

After execution, verify:

1. All ENUMs exist: `SELECT typname FROM pg_type WHERE typname LIKE '%_enum';`
2. All tables exist: `SELECT tablename FROM pg_tables WHERE schemaname = 'public';`
3. RLS is enabled: `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';`
4. Storage bucket exists: Check in Supabase Dashboard → Storage

## Schema Overview

```
profiles (extends auth.users)
  └── user_preferences
  └── courses
      └── course_materials
          └── page_analyses (multimodal analysis results)
      └── learning_units (calendar events)
      └── flashcards
  └── conversations
      └── messages (with context_page_id → page_analyses)
```

## Notes

- The `page_analyses` table is the core of the multimodal approach, storing structured analysis per page
- Storage bucket uses folder structure: `{user_id}/{course_id}/{filename}`
- All timestamps use UTC timezone
- The `messages` table uses `context_page_id` (FK to `page_analyses`) instead of just `page_number` for better data integrity
