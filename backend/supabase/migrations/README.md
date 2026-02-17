# Supabase Migrations

This directory contains database migration files for the Lernkompanien project.

## Migration List

| File | Description |
|------|-------------|
| `20260110111927_initial_schema.sql` | Initial database schema |
| `20260112000000_add_course_material_id_to_learning_units.sql` | Link learning units to materials |
| `20260113000000_add_summary_to_course_materials.sql` | Add summary field |
| `20260126000000_add_slide_snippets.sql` | Add slide snippets table |
| `20260127000000_add_classification_to_course_materials.sql` | Material classification |
| `20260128000000_make_classification_text.sql` | Classification as text |
| `20260131000000_add_knowledge_tracking.sql` | Knowledge tracking tables |
| `20260201000000_add_anki_study_history.sql` | Anki study history |
| `20260202000000_flashcard_anki_cache.sql` | **Flashcard cache (Anki-aligned)** |

---

## Flashcard Anki Cache Migration

**File**: `20260202000000_flashcard_anki_cache.sql`

This migration adds the `flashcard_cache` table - an Anki-aligned cache that serves as the local backup for flashcards stored in Anki.

### What's Included

- **flashcard_cache table**: Mirrors Anki note structure with `anki_note_id`, `deck_name`, `front`, `back`, `tags`
- **Indexes**: Optimized for deck pattern queries and user lookups
- **RLS Policies**: Users can only access their own cached cards
- **Helper functions**: `extract_source_from_tags()`, `extract_page_from_tags()`

### Key Design Decisions

1. **Anki is source of truth**: Cards are added to Anki first, then cached locally
2. **Tags encode metadata**: `page:N` and `source:UUID` stored in tags array (no extra columns)
3. **Deck hierarchy**: Uses Anki's `Parent::Child` naming convention
4. **Bidirectional sync**: `sync_cache_from_anki()` pulls changes from Anki

### Rollback

```sql
DROP TABLE IF EXISTS flashcard_cache CASCADE;
```

### Note on Old Table

The original `flashcards` table is preserved but no longer written to. It can be dropped after production testing confirms the new system works.

---

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
          └── slide_snippets (visual snippets)
      └── learning_units (calendar events)
      └── flashcards (legacy - deprecated)
      └── flashcard_cache (Anki-aligned, current)
  └── conversations
      └── messages (with context_page_id → page_analyses)
  └── anki_study_history (daily study aggregates)
```

### Flashcard Storage Strategy

```
                     ┌─────────────────┐
                     │   AnkiWeb       │  ← Source of truth (cloud)
                     └────────┬────────┘
                              │ sync
                     ┌────────▼────────┐
                     │  Anki Desktop   │  ← Source of truth (local)
                     │   (Docker)      │
                     └────────┬────────┘
                              │ AnkiConnect API
                     ┌────────▼────────┐
                     │ flashcard_cache │  ← Local backup/cache
                     │   (Supabase)    │
                     └─────────────────┘
```

## Notes

- The `page_analyses` table is the core of the multimodal approach, storing structured analysis per page
- Storage bucket uses folder structure: `{user_id}/{course_id}/{filename}`
- All timestamps use UTC timezone
- The `messages` table uses `context_page_id` (FK to `page_analyses`) instead of just `page_number` for better data integrity
