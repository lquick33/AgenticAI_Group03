# StudyBuddy — Exhaustive Feature Specification

> **Purpose**: Definitive catalog of _every_ feature in the codebase, no matter how small.  
> **Use**: Input for architecture pattern decisions (Event-Based, MVC, n-Tier, etc.)

---

## Table of Contents

1. [Domain 1 — PDF Processing & Analysis](#1-pdf-processing--analysis)
2. [Domain 2 — Study Session & Tutoring (Tutor Agent)](#2-study-session--tutoring)
3. [Domain 3 — Flashcard Generation (Flashcard Agent)](#3-flashcard-generation)
4. [Domain 4 — Quiz System (Quiz Agent)](#4-quiz-system)
5. [Domain 5 — Quick Chat & Cross-Course Search](#5-quick-chat--cross-course-search)
6. [Domain 6 — Course & Material Management](#6-course--material-management)
7. [Domain 7 — Anki Desktop Integration](#7-anki-desktop-integration)
8. [Domain 8 — Knowledge Tracking & Analytics](#8-knowledge-tracking--analytics)
9. [Domain 9 — Text-to-Speech](#9-text-to-speech)
10. [Domain 10 — Snippet Management](#10-snippet-management)
11. [Domain 11 — Frontend UI Components](#11-frontend-ui-components)
12. [Domain 12 — Session & Conversation Management](#12-session--conversation-management)
13. [Domain 13 — Observability & Monitoring](#13-observability--monitoring)
14. [Domain 14 — Background Task Infrastructure](#14-background-task-infrastructure)
15. [Domain 15 — Infrastructure & Configuration](#15-infrastructure--configuration)

> **ID Convention**: `F-{domain}.{number}` (e.g. `F-1.1`)

---

## 1. PDF Processing & Analysis

| ID | Feature | Source Files |
|---|---|---|
| F-1.1 | PDF Upload & Storage | `endpoints.py`, `storage.py` |
| F-1.2 | PDF-to-Image Conversion | `pdf_processor.py` |
| F-1.3 | Multimodal Slide Analysis (Gemini Vision) | `analyzer.py` |
| F-1.4 | Background PDF Processing Pipeline | `pdf_processor.py` |
| F-1.5 | Vector Embedding Generation | `embedding_service.py` |
| F-1.6 | Material Summary Generation | `analyzer.py` |

### F-1.1 — PDF Upload & Storage

- **Endpoint**: `POST /courses/{course_id}/materials`
- **Behavior**: Accepts PDF file upload via multipart form. Validates file type (PDF only) and size. Uploads raw PDF bytes to Supabase Storage bucket `course_materials` under path `{user_id}/{filename}`. Creates a `course_materials` DB record with `status: "pending"`. Returns the material ID. Kicks off background processing (F-1.4).
- **Inputs**: `file: UploadFile`, `course_id: str`, `user_id: str`
- **Outputs**: `{ id, file_name, file_path, page_count, status }`
- **Data**: Supabase Storage + `course_materials` table
- **Multi-file**: Supports uploading multiple files in sequence from the frontend `multi-file-upload-list.tsx`.

### F-1.2 — PDF-to-Image Conversion

- **Function**: `convert_from_bytes()` via `pdf2image` library
- **Behavior**: Converts each PDF page into a JPEG `PIL.Image`. Used both for Gemini analysis (F-1.3) and for the `GetPageImageTool` (visual inspection by agent).
- **Output format**: PIL Image objects, optionally converted to base64 Data URI via `pil_image_to_bytes()` + `image_bytes_to_base64()`.

### F-1.3 — Multimodal Slide Analysis (Gemini Vision)

- **Function**: `analyze_pdf_page()` in `analyzer.py`
- **Behavior**: Sends a page image (base64) to Google Gemini vision model (`gemini-2.5-flash`, fallback `gemini-1.5-flash`). Returns structured analysis via Pydantic `SlideAnalysis` model.
- **Output fields**:
  - `summary` — Free-text page summary
  - `key_terms` — List of key terms/concepts
  - `exam_questions` — Suggested exam questions
  - `diagram_description` — Description of any diagrams/charts on the page
  - `chapter_title` — Detected chapter/section title
- **Tracing**: Instrumented with Langfuse callback handler for token tracking.

### F-1.4 — Background PDF Processing Pipeline

- **Function**: `process_pdf_background()` in `pdf_processor.py`
- **Behavior**: Orchestrates the full processing of an uploaded PDF:
  1. Sets material status to `processing`
  2. Converts PDF to page images
  3. Processes pages in parallel (configurable concurrency, default 5 via `asyncio.Semaphore`)
  4. For each page: calls `analyze_pdf_page()` → `save_page_analysis()` to Supabase
  5. Generates material-level summary via `generate_material_summary()` (F-1.6)
  6. Auto-generates filename from first page summary via `generate_material_filename()`
  7. Detects naming patterns from existing files in the course
  8. Triggers background embedding generation (F-1.5)
  9. Sets material status to `completed` (or `failed`)
- **Concurrency**: `max_concurrent=5` by default
- **Error handling**: Individual page failures don't block other pages. Final status reflects partial success.

### F-1.5 — Vector Embedding Generation

- **Service**: `embedding_service.py`
- **Behavior**: After PDF processing completes, generates 768-dim vector embeddings for each page summary using Google `text-embedding-004` model. Embeddings stored in `page_analyses.embedding` column. Enables semantic/hybrid search in Quick Chat (F-5.2).
- **Functions**:
  - `generate_embedding(text)` — Single text
  - `generate_embeddings_batch(texts)` — Batch mode (up to 100)
  - `generate_embeddings_for_material(material_id)` — Full material pipeline
  - `save_embedding(page_id, embedding)` — Persist to DB
  - `check_embedding_availability()` — Verify API key is configured

### F-1.6 — Material Summary Generation

- **Function**: `generate_material_summary()` in `analyzer.py`
- **Behavior**: After all pages are analyzed, aggregates all page summaries/key_terms and generates a global lecture summary via Gemini LLM. The summary is JSON-encoded and stored in `course_materials.summary`. Returns a structured overview of the lecture's topics, concepts, and themes.
- **Used by**: TutorAgent and QuickChatAgent for initial lecture context.

---

## 2. Study Session & Tutoring

| ID | Feature | Source Files |
|---|---|---|
| F-2.1 | Study Session Initiation | `endpoints.py` (`initiate_chat`) |
| F-2.2 | SSE Chat Streaming | `endpoints.py` |
| F-2.3 | Tutor Agent (LangGraph) | `tutor_agent.py` |
| F-2.4 | Page Navigation via Human Messages | `endpoints.py` |
| F-2.5 | Context-Aware Responses | `tutor_agent.py` |
| F-2.6 | Personality Configuration | `tutor_agent.py` |
| F-2.7 | State-Aware Tool Injection | `tutor_agent.py` |
| F-2.8 | Message History Persistence | `session_storage.py`, `storage.py` |
| F-2.9 | Conversation Progress Tracking | `session_storage.py` |
| F-2.10 | Incomplete Tool Call Fixing | `tutor_agent.py` |

### F-2.1 — Study Session Initiation

- **Endpoint**: `POST /chat`
- **Function**: `initiate_chat()` — 925 lines
- **Behavior**: The central orchestration function. Receives a chat request, loads/creates conversation, resolves page context, invokes the appropriate agent (Tutor or QuickChat), and streams the response back via SSE.
- **Inputs**: `InitiateChatRequest { user_id, material_id, page, message, course_id, conversation_id, session_type }`
- **Logic**:
  1. Validates input, resolves `session_type` (study vs quickchat)
  2. Loads existing conversation + message history from DB
  3. Fetches page analysis data for context injection
  4. Constructs LangGraph state with `current_page`, `material_id`, `user_id`, `course_material_summary`
  5. Invokes appropriate agent graph
  6. Streams response tokens via SSE with event types: `message`, `quiz`, `navigation`, `tts`, `error`, `done`
  7. Persists user + assistant messages to DB after completion

### F-2.2 — SSE Chat Streaming

- **Endpoint**: `POST /chat` (returns `StreamingResponse`)
- **Behavior**: Uses Server-Sent Events to stream agent responses token-by-token to the frontend. Different event types carry different payloads:
  - `event: message` → `{ content: "..." }` — Text chunk
  - `event: quiz` → `{ quiz_id: "...", quiz_data: {...} }` — Inline quiz
  - `event: navigation` → `{ page: N }` — Page navigation request
  - `event: tts` → `{ audio_base64: "..." }` — TTS audio data
  - `event: error` → `{ error: "..." }` — Error message
  - `event: done` → `{}` — Stream end
- **Frontend handler**: `lib/api/study.ts` → `EventQueue` pattern in `lib/event-queue.ts`

### F-2.3 — Tutor Agent (LangGraph)

- **Class**: `TutorAgent` in `tutor_agent.py` (967 lines)
- **Architecture**: LangGraph `StateGraph` with nodes:
  - `call_model` — Invokes Gemini LLM with current state + messages
  - `tools` — `StateAwareToolNode` for tool execution
- **Conditional edges**: `should_continue()` routes to `tools` or `END`
- **Special behavior**: After a `create_quiz` tool call completes, the graph always ends (quiz is returned to user).
- **System prompt**: Loaded from Langfuse (`tutor-agent/system-prompt`), with fallback hardcoded prompt. Compiled with personality variables.
- **Token optimization**: Caches enhanced system prompt via `_compute_state_hash()`. Only rebuilds if state (page, material) changes.
- **Tools available**:
  - `get_page_analysis` — Retrieve slide content
  - `get_page_image` — Visual slide inspection
  - `get_course_material_summary` — Lecture overview
  - `create_quiz` — Generate comprehension quiz
  - `text_to_speech` — Generate audio
  - `get_course_knowledge` — Check student knowledge levels

### F-2.4 — Page Navigation via Human Messages

- **Behavior**: When the user navigates to a new page in the PDF viewer, the frontend sends a special message `"next Page: {N}"` (literal `HumanMessage`). The Tutor Agent detects this and automatically fetches the analysis for the new page.
- **Design rationale**: Uses a human message instead of LangGraph conditional edges to keep the agent reactive to user-driven page changes naturally.

### F-2.5 — Context-Aware Responses

- **Behavior**: The agent's system prompt is dynamically enhanced with:
  - Current page analysis (summary, key_terms, exam_questions, diagram_description)
  - Material summary (global lecture overview)
  - Current page number
  - Custom context from slide snippets
- **Implementation**: `_build_enhanced_system_prompt()` inside `call_model()` rebuilds the system message on each invocation with fresh state.

### F-2.6 — Personality Configuration

- **Behavior**: The Tutor Agent's communication style is configurable via three axes:
  - `formality`: "formal" | "casual" | "balanced"
  - `humor`: "none" | "moderate" | "high"
  - `encouragement`: "minimal" | "moderate" | "high"
- **Implementation**: `_get_personality_texts()` maps config values to natural language descriptions injected into the system prompt. Supports both German and English.
- **Frontend**: Settings dialog at `components/settings/settings-dialog.tsx`

### F-2.7 — State-Aware Tool Injection

- **Class**: `StateAwareToolNode` in `tutor_agent.py` (duplicated in `quickchat_agent.py`)
- **Behavior**: Intercepts tool calls from the LLM and replaces parameter values with actual state values. Prevents the LLM from hallucinating UUIDs and IDs.
  - Injects `course_material_id` → from `state.material_id`
  - Injects `page_number` → from `state.current_page`
  - Injects `user_id` → from `state.user_id`
  - Injects `course_id` → from `state.course_id`
- **Why**: LLMs frequently hallucinate UUID values when asked to call tools with ID parameters.

### F-2.8 — Message History Persistence

- **Service**: `session_storage.py`
- **Behavior**: Stores conversation messages in `messages` table:
  - `conversation_id` — FK to conversations
  - `role` — "user" | "assistant" | "system"
  - `content` — Message text
  - `context_page_id` — Optional FK to `page_analyses.id`
  - `created_at` — Timestamp
- **Loading**: `load_conversation_with_messages()` returns last N messages (default 50), ordered oldest-first.

### F-2.9 — Conversation Progress Tracking

- **Function**: `update_conversation_progress(conversation_id, last_page_number)`
- **Behavior**: Stores the user's last visited page in conversation metadata (`conversations.metadata.last_page_number`). Allows resuming study sessions from the last viewed page.

### F-2.10 — Incomplete Tool Call Fixing

- **Function**: `_fix_incomplete_tool_calls()` in `tutor_agent.py` (duplicated in `endpoints.py`)
- **Behavior**: Validates and fixes message ordering to comply with Gemini API requirements. Gemini requires strict ordering (User → AI → ToolCall → ToolResult). This function patches any orphaned tool calls or missing tool results.

---

## 3. Flashcard Generation

| ID | Feature | Source Files |
|---|---|---|
| F-3.1 | Flashcard Generation Agent | `flashcard_agent.py` |
| F-3.2 | Material Classification | `classifier.py`, `flashcard_agent.py` |
| F-3.3 | Page Skip Decision (Autonomous) | `flashcard_agent.py` |
| F-3.4 | Parallel Skip Evaluation | `flashcard_agent.py` |
| F-3.5 | Context-Aware Card Generation | `flashcard_agent.py` |
| F-3.6 | Classification-Specific Prompts | `flashcard_agent.py` |
| F-3.7 | Deduplication (Anki-Aware) | `flashcard_agent.py` |
| F-3.8 | Flashcard Caching to DB | `storage.py` |
| F-3.9 | Progress Tracking & Callbacks | `flashcard_task_service.py` |
| F-3.10 | Task Cancellation | `flashcard_task_service.py` |
| F-3.11 | Anki APKG Export | `flashcard_service.py` |

### F-3.1 — Flashcard Generation Agent

- **Class**: `FlashcardGeneratorAgent` in `flashcard_agent.py` (2289 lines)
- **Architecture**: LangGraph `StateGraph` with nodes:
  1. `initialize` — Load page analyses, prefetch messages, classify material
  2. `classify` — Run material classification + parallel skip decisions
  3. `process_page` — Set current page context
  4. `skip_decision` — Look up pre-evaluated skip decision
  5. `get_context` — Load conversation messages + snippet URLs for current page
  6. `generate_cards` — Call LLM to generate flashcards
  7. `update_progress` — Increment page index
  8. `save_cards` — Deduplicate + save to Anki + cache to DB
- **Conditional edges**:
  - `should_skip_routing` → "skip" or "generate"
  - `check_more_pages` → "continue" or "done"
- **State checkpointing**: Uses `PostgresSaver` (persistent) or `MemorySaver` (fallback) for resumability.

### F-3.2 — Material Classification

- **Service**: `classifier.py`
- **Behavior**: Classifies material into domain categories using Gemini LLM with structured output:
  - `language_learning` — Vocabulary, grammar, translations
  - `math` — Formulas, equations, proofs
  - `business_administration` — Case studies, strategy, marketing
  - `general` — Default/mixed content
- **Output**: `{ category, confidence (0.0-1.0), reasoning }`
- **Stored in**: `course_materials.classification`, `classification_confidence`, `classification_reasoning`
- **Caching**: In-memory cache with 1-hour TTL via `get_material_classification()` in `storage.py`
- **Override**: Users can manually override classification via `update_material_classification()`

### F-3.3 — Page Skip Decision (Autonomous)

- **Behavior**: For each page, the agent autonomously decides whether to skip flashcard generation. Skip reasons include:
  - Title-only slides
  - Table of contents pages
  - Pages with only organizational information
  - Pages already covered by existing flashcards
- **Implementation**: `skip_decision_node()` looks up pre-computed decisions. Uses Langfuse prompt `flashcard-agent/skip-decision` with fallback.

### F-3.4 — Parallel Skip Evaluation

- **Function**: `_evaluate_skip_decisions_parallel()` in `flashcard_agent.py`
- **Behavior**: Uses `ThreadPoolExecutor` (default `max_workers=5`) to evaluate all page skip decisions concurrently rather than sequentially. Runs during the `classify` node to amortize latency.
- **Performance gain**: N sequential LLM calls → N/5 wall-clock time.

### F-3.5 — Context-Aware Card Generation

- **Node**: `generate_cards_node()`
- **Behavior**: Generates flashcards for a single page using:
  - Page analysis (summary, key_terms, exam_questions, diagram_description)
  - Conversation context (tutor messages for this page from study session)
  - Snippet image URLs (user-cropped slide images)
  - Material classification (to tailor card style)
- **Output**: List of `{ front, back, tags, source_page_analysis_id }` dicts.
- **Image inclusion**: When snippet URLs exist, they are embedded in the card back as `<img>` tags.

### F-3.6 — Classification-Specific Prompts

- **Function**: `_get_classification_specific_prompt()` in `flashcard_agent.py`
- **Behavior**: Loads domain-specific flashcard generation prompts from Langfuse:
  - `flashcard-agent/language-learning` — Vocab cards with pinyin/characters
  - `flashcard-agent/math` — Formula cards with derivation steps
  - `flashcard-agent/business_administration` — Concept cards with examples
  - `flashcard-agent/base-prompt` — Generic/fallback
- **Composition**: Some prompts use `{{base_prompt_content}}` variable to extend the base prompt. Others are standalone.

### F-3.7 — Deduplication (Anki-Aware)

- **Behavior**: Before saving new cards, compares against existing Anki card fronts:
  1. `sync_cache_from_anki()` — Pulls current Anki state into local cache
  2. `_load_existing_fronts_from_anki()` — Gets all card fronts from the target deck
  3. Compares new card fronts against existing ones
  4. Only adds truly new cards
- **Course-wide dedup**: Optional `deduplicate_course` flag enables cross-lecture deduplication within the parent deck.

### F-3.8 — Flashcard Caching to DB

- **Functions**: `cache_flashcards()`, `get_cached_flashcards()` in `storage.py`
- **Behavior**: Stores generated flashcards in Supabase `flashcard_cache` table as a fallback. If Anki is unavailable, cards are still saved. Allows download as `.apkg` later.
- **Fields**: `front`, `back`, `tags`, `page_analysis_id`, `deck_name`, `course_material_id`, `user_id`

### F-3.9 — Progress Tracking & Callbacks

- **Service**: `FlashcardTaskService` in `flashcard_task_service.py`
- **Behavior**: Manages in-memory task state for flashcard generation:
  - `create_task()` → Returns a `FlashcardTask` with `task_id`
  - `_run_task()` → Executes generation in background `asyncio.Task`
  - `progress_callback()` → Called after each page, updates task with:
    - `current_page_index`, `total_pages`, `processed_pages`, `skipped_pages`, `cards_generated`, `progress` (0-100%)
- **Frontend polling**: `GET /flashcards/tasks/{task_id}/status` returns live progress.

### F-3.10 — Task Cancellation

- **Endpoint**: `POST /flashcards/tasks/{task_id}/cancel`
- **Behavior**: Sets `task._cancelled = True`. The agent checks this flag between pages and stops gracefully if cancelled.

### F-3.11 — Anki APKG Export

- **Service**: `flashcard_service.py` (276 lines)
- **Function**: `build_anki_apkg(cards, deck_name)` 
- **Behavior**: Constructs an Anki `.apkg` file (SQLite + ZIP format) from card data. Downloads and embeds snippet images directly into the package (not as URLs).
- **Endpoint**: `GET /flashcards/{course_material_id}/download`

---

## 4. Quiz System

| ID | Feature | Source Files |
|---|---|---|
| F-4.1 | Quiz Generation Agent | `quiz_generator_agent.py` |
| F-4.2 | Quiz Persistence | `quiz_service.py` |
| F-4.3 | Quiz Submission & Scoring | `quiz_service.py`, `endpoints.py` |
| F-4.4 | Quiz Creation Lock | `quiz_creation_lock.py` |
| F-4.5 | Post-Quiz Tutor Feedback | `endpoints.py` |
| F-4.6 | Quiz Validation | `quiz_generator_agent.py`, `lib/quiz-validation.ts` |

### F-4.1 — Quiz Generation Agent

- **Class**: `QuizGeneratorAgent` in `quiz_generator_agent.py` (597 lines)
- **Architecture**: LangGraph `StateGraph` with single node `generate_node`
- **Behavior**: Generates 3-5 multiple-choice comprehension questions from page analyses within a page range. Questions focus on understanding, not memorization.
- **Inputs**: `start_page`, `end_page`, `course_material_id`, `user_id`
- **Output**: `QuizData` Pydantic model with list of `QuizQuestion` (each has `question`, `options: {A, B, C, D}`, `correct_answer`, `explanation`)
- **Prompt**: Loaded from Langfuse (`quiz-agent/system-prompt`), with fallback.
- **Validation**: `_validate_quiz()` ensures minimum 3 questions, valid correct answers, non-empty options.
- **LLM**: Uses `with_structured_output(QuizData)` for reliable JSON output.

### F-4.2 — Quiz Persistence

- **Service**: `quiz_service.py`
- **Function**: `save_quiz()` — Saves quiz data to `quizzes` table
- **Fields**: `quiz_data` (JSONB), `course_material_id`, `user_id`, `start_page`, `end_page`, `topic_name`, `conversation_id`, `status`

### F-4.3 — Quiz Submission & Scoring

- **Endpoint**: `POST /quiz/submit`
- **Function**: `submit_quiz_results()` in `quiz_service.py`
- **Behavior**:
  1. Loads quiz from DB
  2. Validates quiz hasn't been submitted before
  3. `calculate_score()` compares user answers against correct answers
  4. Generates per-question `QuestionResult` with `is_correct`, `explanation`
  5. Saves `QuizResult` to `quiz_results` table
  6. Returns score + detailed results
- **Post-submit**: Triggers tutor feedback generation (F-4.5)

### F-4.4 — Quiz Creation Lock

- **Service**: `QuizCreationLock` in `quiz_creation_lock.py`
- **Behavior**: Thread-safe lock preventing race conditions during quiz creation:
  - `acquire_lock(material_id, user_id, start_page, end_page)` — Prevents concurrent quiz generation
  - `release_lock()` — After quiz is created or fails
  - `is_locked()` — Check before starting new quiz
  - `cleanup_expired_locks()` — Auto-cleanup locks older than 5 minutes
- **Scope**: Prevents user from generating quiz while another is in progress for the same material.

### F-4.5 — Post-Quiz Tutor Feedback

- **Behavior**: After quiz submission, the tutor agent receives the quiz results and generates personalized feedback. This feedback includes:
  - Which questions were wrong and why
  - Suggestions for what to review
  - Encouragement based on score
- **Implementation**: Inside `submit_quiz()` endpoint, a follow-up tutor invocation is made with quiz results injected as context.

### F-4.6 — Quiz Validation (Frontend + Backend)

- **Backend**: `_validate_quiz()` and `_parse_quiz_result()` in `quiz_generator_agent.py`
  - Validates question count (≥3), option completeness, correct answer exists
- **Frontend**: `lib/quiz-validation.ts` (5KB)
  - Validates quiz data structure before rendering
  - Ensures all required fields are present
  - Handles edge cases from SSE parsing

---

## 5. Quick Chat & Cross-Course Search

| ID | Feature | Source Files |
|---|---|---|
| F-5.1 | Quick Chat Agent | `quickchat_agent.py` |
| F-5.2 | Hybrid Search (Vector + Keyword) | `search_topic_tool.py`, `storage.py` |
| F-5.3 | LLM-Based Keyword Extraction | `search_topic_tool.py` |
| F-5.4 | Intro Page Scoring Algorithm | `search_topic_tool.py` |
| F-5.5 | Dual-Mode Operation | `quickchat_agent.py` |
| F-5.6 | Cross-Course Navigation | `quickchat_agent.py` |
| F-5.7 | Message Truncation | `quickchat_agent.py` |

### F-5.1 — Quick Chat Agent

- **Class**: `QuickChatAgent` in `quickchat_agent.py` (535 lines)
- **Architecture**: LangGraph `StateGraph`, same pattern as TutorAgent
- **Difference from TutorAgent**: Operates in two modes and has `SearchTopicTool` + `GetUserCoursesTool` as additional tools.
- **System prompt**: Loaded from Langfuse (`quickchat-agent/system-prompt`), with personality support.

### F-5.2 — Hybrid Search (Vector + Keyword)

- **Tool**: `SearchTopicTool._run()` in `search_topic_tool.py` (1006 lines)
- **Behavior**: Searches across ALL of a user's courses and materials for a topic:
  1. Extracts search keywords via LLM (F-5.3)
  2. Calls `search_page_analyses_hybrid()` in `storage.py`
  3. Hybrid search combines:
     - **Vector similarity** — Cosine similarity on `page_analyses.embedding` (768-dim)
     - **Full-text search** — PostgreSQL `tsvector` on summary + key_terms
  4. Returns ranked results with course/material/page context
- **Output per result**: `{ course_title, material_name, page_number, summary, key_terms, chapter_title, similarity_score }`

### F-5.3 — LLM-Based Keyword Extraction

- **Functions**: `_extract_keywords_sync()`, `_extract_keywords_async()` in `SearchTopicTool`
- **Behavior**: Uses Gemini LLM to extract searchable keywords from a natural language query. Extracts both German AND English terms, including synonyms and related technical terms.
- **Example**: `"How do I draw a class diagram?"` → `["Klassendiagramm", "class diagram", "UML", "Klasse"]`

### F-5.4 — Intro Page Scoring Algorithm

- **Function**: `_pick_best_intro_page()` in `SearchTopicTool` (~400 lines)
- **Behavior**: Multi-strategy algorithm to find the FIRST page where a topic is INTRODUCED (not just mentioned):
  - **Lowest page heuristic** — Prefer earlier pages
  - **Title match scoring** — Chapter titles matching the query score higher
  - **Key term match scoring** — Fuzzy/stem-based matching
  - **Topic correlation scoring** — How much the page content correlates to the query
  - **LLM refinement** — Optional LLM call via `_pick_best_intro_page_with_llm()` to pick best from top candidates
- **Weighted aggregate**: Combines all scores with configurable weights.
- **Debug endpoint**: `run_search_and_return_score_breakdown()` returns full score details.

### F-5.5 — Dual-Mode Operation

- **Behavior**: The QuickChatAgent transitions between two modes:
  1. **Discovery Mode**: User asks about a topic → Agent searches across courses → Presents matching pages with context
  2. **Tutoring Mode**: User navigates to a found page → Agent switches to tutoring behavior, answering questions about specific page content
- **State fields**: `current_page`, `material_id`, `course_id` track current context for tutoring mode.

### F-5.6 — Cross-Course Navigation

- **State field**: `navigation_request: Optional[Dict[str, Any]]`
- **Behavior**: When the agent finds a relevant page, it can emit a navigation request that tells the frontend to open the specific material at the specific page.
- **SSE event**: `event: navigation` → `{ page, material_id, course_id }`

### F-5.7 — Message Truncation

- **Function**: `_truncate_messages_for_llm()` in `QuickChatAgent`
- **Behavior**: Truncates message history to prevent token explosion. Keeps the system message + most recent messages. Ensures tool call / tool result pairs are kept together.

---

## 6. Course & Material Management

| ID | Feature | Source Files |
|---|---|---|
| F-6.1 | Course CRUD | `endpoints.py`, `storage.py` |
| F-6.2 | Material Upload (Multi-file) | `endpoints.py` |
| F-6.3 | Material Rename | `endpoints.py`, `storage.py` |
| F-6.4 | Material Delete (Cascade) | `endpoints.py`, `storage.py` |
| F-6.5 | Course Rename | `endpoints.py`, `storage.py` |
| F-6.6 | Exam Date Management | `endpoints.py`, `storage.py` |
| F-6.7 | Material Processing Status | `endpoints.py`, `storage.py` |
| F-6.8 | Auto-Generated Filenames | `analyzer.py` |
| F-6.9 | Naming Pattern Detection | `analyzer.py` |
| F-6.10 | Course Settings | `endpoints.py` |

### F-6.1 — Course CRUD

- **Create**: `POST /courses` — Creates a course with `title`, `user_id`
- **Read**: `GET /courses` — List all courses for user, `GET /courses/{id}` — Single course with materials
- **Update**: `PUT /courses/{id}` — Update title, exam_date
- **Delete**: `DELETE /courses/{id}` — Cascade delete all materials, analyses, flashcards
- **Data**: `courses` table with `id`, `title`, `user_id`, `exam_date`, `created_at`

### F-6.3 — Material Rename

- **Endpoint**: `PUT /courses/materials/{material_id}`
- **Behavior**: Updates `file_name` in `course_materials` table. If Anki decks exist, triggers `on_material_renamed()` to rename the corresponding Anki deck (`storage.py`).

### F-6.4 — Material Delete (Cascade)

- **Endpoint**: `DELETE /courses/materials/{material_id}`
- **Function**: `delete_course_material()` in `storage.py`
- **Cascade order**:
  1. Get material record (verify ownership)
  2. Get associated page analysis IDs
  3. Delete flashcards linked to those page analyses
  4. Delete page analyses
  5. Delete snippets
  6. Delete quiz data
  7. Delete messages referencing page analyses
  8. Delete file from Supabase Storage
  9. Delete Anki deck mappings
  10. Delete material record

### F-6.5 — Course Rename

- **Behavior**: When a course title is changed, `on_course_renamed()` in `storage.py` updates all Anki deck names that use the old course title as parent deck.

### F-6.8 — Auto-Generated Filenames

- **Function**: `generate_material_filename()` in `analyzer.py`
- **Behavior**: After first page analysis, uses Gemini LLM to generate a descriptive filename from the page 1 summary. Considers existing naming patterns (F-6.9) for consistency.
- **Example output**: `"Kapitel 3: Objektorientierte Programmierung"`

### F-6.9 — Naming Pattern Detection

- **Function**: `detect_naming_pattern()` in `analyzer.py`
- **Behavior**: Analyzes existing filenames in a course to detect patterns:
  - `"Kapitel {n}: {topic}"` → Next file: `"Kapitel 4: ..."`
  - `"Lecture {n} - {topic}"` → Next file: `"Lecture 5 - ..."`
  - `"Vorlesung {n}"` → Next file: `"Vorlesung 6"`
- **Used by**: `generate_material_filename()` to maintain consistent naming.

---

## 7. Anki Desktop Integration

| ID | Feature | Source Files |
|---|---|---|
| F-7.1 | Anki Docker Container | (infrastructure) |
| F-7.2 | AnkiConnect API Client | `services/anki/client.py` |
| F-7.3 | Add Cards to Anki | `anki_tools.py`, `flashcard_agent.py` |
| F-7.4 | Batch Card Creation | `anki_tools.py` |
| F-7.5 | Search Anki Cards | `anki_tools.py` |
| F-7.6 | AnkiWeb Sync | `endpoints.py`, `anki_tools.py` |
| F-7.7 | AnkiWeb Login/Logout | `endpoints.py` |
| F-7.8 | Force Full Sync | `endpoints.py` |
| F-7.9 | Deck Management | `anki_tools.py`, `storage.py` |
| F-7.10 | Anki Study History Sync | `storage.py`, `endpoints.py` |

### F-7.1 — Anki Docker Container

- **Behavior**: Runs Anki desktop in a headless Docker container with AnkiConnect add-on exposed on port 8765. Allows programmatic flashcard management without requiring user's local Anki installation.

### F-7.3 — Add Cards to Anki

- **Functions**: `create_flashcard()`, `create_course_flashcard()` in `anki_tools.py`
- **Behavior**: Creates Anki notes via AnkiConnect API. Supports:
  - Custom deck names (e.g., `"Marketing 101::Lecture 3"`)
  - Tags per card
  - Optional immediate AnkiWeb sync
  - Automatic deck creation if deck doesn't exist
- **Course-aware**: `create_course_flashcard()` auto-generates deck name as `"Course Title::Lecture Name"` from course/material IDs.

### F-7.5 — Search Anki Cards

- **Function**: `search_anki_cards(query)` in `anki_tools.py`
- **Behavior**: Searches existing cards using Anki's query syntax (`deck:DeckName`, `tag:tagname`, `-is:suspended`, etc.)
- **Use case**: Deduplication, knowledge level assessment

### F-7.6 — AnkiWeb Sync

- **Endpoint**: `POST /anki/sync`
- **Behavior**: Triggers normal bi-directional sync with AnkiWeb. Fails if full sync is required (conflict).
- **Background sync**: `_add_cards_to_anki()` in flashcard agent runs sync in background thread to avoid blocking.

### F-7.7 — AnkiWeb Login/Logout

- **Endpoints**: `POST /anki/login`, `POST /anki/logout`, `GET /anki/login-status`
- **Behavior**: Authenticates with AnkiWeb using email/password. Stores only auth token (hkey), not password.
- **Rate limiting**: 5 login attempts per 15 minutes per IP.
- **Status caching**: Login status cached for 30s TTL to avoid slow Docker/AnkiConnect checks.

### F-7.10 — Anki Study History Sync

- **Functions**: `sync_anki_study_history()`, `upsert_study_history()` in `storage.py`
- **Endpoint**: `GET /anki/study-history`
- **Behavior**: Pulls daily study statistics from Anki:
  - Cards reviewed per day
  - Time spent studying
  - Button press breakdown (Again/Hard/Good/Easy)
  - New/review/relearn card counts
  - Average time per card
- **Data**: Stored in `anki_study_history` table, up to 365 days.

---

## 8. Knowledge Tracking & Analytics

| ID | Feature | Source Files |
|---|---|---|
| F-8.1 | Deck-Level Knowledge Scores | `anki_tools.py`, `services/anki/` |
| F-8.2 | Course-Level Knowledge Breakdown | `anki_tools.py`, `knowledge_tool.py` |
| F-8.3 | Knowledge Snapshots | `storage.py` |
| F-8.4 | Deck-Course Mappings | `storage.py` |
| F-8.5 | Study Progress Charts | `components/dashboard/progress-chart.tsx` |
| F-8.6 | KPI Dashboard Cards | `components/dashboard/kpi-cards.tsx` |

### F-8.1 — Deck-Level Knowledge Scores

- **Function**: `get_knowledge_levels()` in `anki_tools.py`
- **Behavior**: Calculates mastery score (0.0–1.0) for each Anki deck based on:
  - Card states (new, learning, review, suspended)
  - Ease factors
  - Retention rate
  - Interval distribution
- **Status labels**: "mastered", "progressing", "needs_review", "not_started"
- **Recommendations**: Auto-generated suggestions like "Focus on 'Lecture 3' - low retention rate"

### F-8.2 — Course-Level Knowledge Breakdown

- **Function**: `get_course_knowledge_levels()` in `anki_tools.py`
- **Tool**: `GetCourseKnowledgeTool` (available to TutorAgent and QuickChatAgent)
- **Behavior**: Aggregates per-lecture mastery within a course:
  - Course-level overall mastery (weighted by card count)
  - Per-lecture mastery breakdown
  - Identifies weakest and strongest lectures
- **Used by agents**: To personalize tutoring based on knowledge gaps.

### F-8.3 — Knowledge Snapshots

- **Functions**: `save_knowledge_snapshot()`, `get_latest_knowledge_snapshot()`, `get_knowledge_snapshots_for_course()` in `storage.py`
- **Behavior**: Point-in-time snapshots of knowledge levels, enabling trend tracking over time.
- **Fields**: `total_cards`, `new_cards`, `learning_cards`, `review_cards`, `mastery_score`, `retention_rate`, `avg_interval_days`

### F-8.5 — Study Progress Charts

- **Component**: `components/dashboard/progress-chart.tsx` (12.5KB)
- **Behavior**: Interactive area chart showing study activity over time. Uses Anki study history data. Lazy-loaded via `progress-chart-lazy.tsx`.

### F-8.6 — KPI Dashboard Cards

- **Component**: `components/dashboard/kpi-cards.tsx` (12.9KB)
- **Behavior**: Dashboard section cards showing key metrics:
  - Total courses
  - Total materials
  - Cards reviewed today
  - Study streak
  - Overall mastery percentage

---

## 9. Text-to-Speech

| ID | Feature | Source Files |
|---|---|---|
| F-9.1 | Text-to-Speech Generation | `tts_service.py`, `tts_tool.py` |
| F-9.2 | Multi-Language Support | `tts_service.py` |
| F-9.3 | Flashcard Audio Generation | `tts_service.py` |

### F-9.1 — Text-to-Speech Generation

- **Service**: `tts_service.py` via Google Cloud Text-to-Speech API
- **Tool**: `TextToSpeechTool` — LangChain-compatible tool for agents
- **Behavior**: Converts text to MP3 audio. Returned as base64-encoded bytes. Streamed to frontend via SSE `event: tts`.
- **Parameters**: `text`, `voice_name` (optional), `language_code` (optional, default from settings), `speaking_rate` (0.25–4.0)

### F-9.2 — Multi-Language Support

- **Supported**: German (`de-DE`), English (`en-US`), Chinese (`zh-CN`), Spanish (`es-ES`), French (`fr-FR`), and all Google Cloud TTS languages.
- **Voice fallback**: If specified voice is unavailable, falls back to Google's default for the language.

### F-9.3 — Flashcard Audio Generation

- **Function**: `generate_flashcard_audio()` in `tts_service.py`
- **Behavior**: Generates audio for both character and sentence on Chinese flashcards. Checks for Chinese character presence before generating.

---

## 10. Snippet Management

| ID | Feature | Source Files |
|---|---|---|
| F-10.1 | Snippet Upload | `snippet_service.py`, `endpoints.py` |
| F-10.2 | Snippet Retrieval | `snippet_service.py`, `endpoints.py` |
| F-10.3 | Snippet Deletion | `snippet_service.py`, `endpoints.py` |
| F-10.4 | Snippet in Flashcards | `flashcard_agent.py`, `flashcard_service.py` |

### F-10.1 — Snippet Upload

- **Endpoint**: `POST /snippets`
- **Behavior**: User crops a region from a PDF slide → uploads as image. Stored in Supabase Storage under `{user_id}/snippets/{material_id}/{filename}`. DB record in `slide_snippets` table with `course_material_id`, `page_number`, `image_path`, `order_index`.
- **Multiple per page**: Supports multiple snippets per page.

### F-10.4 — Snippet in Flashcards

- **Behavior**: When generating flashcards, snippets for the current page are fetched and their image URLs are passed to the LLM prompt. The generated card's back side includes `<img>` tags with the snippet images embedded.
- **APKG handling**: When exporting as `.apkg`, snippet images are downloaded from Supabase and embedded directly into the Anki package file.

---

## 11. Frontend UI Components

| ID | Component | File | Key Features |
|---|---|---|---|
| F-11.1 | PDF Viewer | `study/pdf-viewer.tsx` | Renders PDF pages, page navigation |
| F-11.2 | Chat Interface | `study/chat-interface.tsx` | Message display, user input, loading states |
| F-11.3 | Chat Message | `study/chat-message.tsx` | Markdown rendering, inline sources with icons, clickable |
| F-11.4 | Quiz Component | `study/quiz-component.tsx` | Multiple-choice UI, answer selection, results display |
| F-11.5 | Study Reader | `study/study-reader.tsx` | Split-pane layout: PDF + Chat side-by-side |
| F-11.6 | Snippet Overlay | `study/snippet-overlay.tsx` | Crop tool for selecting slide regions |
| F-11.7 | Congratulations Screen | `study/congratulations-screen.tsx` | Shown after completing a study session |
| F-11.8 | Deck Completion Dialog | `study/deck-completion-dialog.tsx` | Shown when flashcard generation completes |
| F-11.9 | Upload Section | `courses/upload-section.tsx` | Drag-and-drop PDF upload with progress |
| F-11.10 | Course Materials List | `courses/course-materials-list.tsx` | Material list with status, rename, delete |
| F-11.11 | Settings Dialog | `settings/settings-dialog.tsx` | Language, personality, Anki config |
| F-11.12 | Background Tasks Indicator | `background-tasks/` | Global task progress indicator + context |

### F-11.2 — Chat Interface

- **Component**: `study/chat-interface.tsx` (8.5KB)
- **Behavior**: Renders chat message list, handles user text input, shows loading spinner during agent processing. Integrates with `EventQueue` for SSE event processing.

### F-11.4 — Quiz Component

- **Component**: `study/quiz-component.tsx` (12.2KB)
- **Behavior**: Renders quiz questions inline in the chat. User selects answers via radio buttons. Submit button sends answers to backend. Displays per-question results with correct/incorrect indicators and explanations.

### F-11.9 — Upload Section

- **Component**: `courses/upload-section.tsx` (23.6KB)
- **Behavior**: Full upload flow with:
  - Drag-and-drop zone for PDF files
  - Multi-file queue (`multi-file-upload-list.tsx`)
  - Real-time upload progress
  - Processing status polling
  - Auto-refresh when processing completes

### F-11.11 — Settings Dialog

- **Component**: `settings/settings-dialog.tsx` (23.9KB)
- **Behavior**: Global settings panel with:
  - Language selection (DE/EN)
  - Personality sliders (formality, humor, encouragement)
  - Anki connection settings
  - AnkiWeb login/logout

### F-11.12 — Background Tasks System

- **Components**: `background-tasks-context.tsx` (14.4KB), `background-tasks-indicator.tsx` (8.7KB)
- **Behavior**: React Context providing global task management:
  - Tracks active flashcard generation tasks
  - Polls task status periodically
  - Shows progress in a persistent UI indicator
  - Handles task completion/failure notifications

---

## 12. Session & Conversation Management

| ID | Feature | Source Files |
|---|---|---|
| F-12.1 | Conversation Get/Create | `session_storage.py` |
| F-12.2 | Message Append | `session_storage.py` |
| F-12.3 | Conversation Load | `session_storage.py` |
| F-12.4 | Progress Update | `session_storage.py` |
| F-12.5 | Conversation Resolution | `storage.py`, `endpoints.py` |

### F-12.1 — Conversation Get/Create

- **Function**: `get_or_create_study_conversation()` in `session_storage.py`  
- **Behavior**: Finds existing or creates new conversation identified by `(user_id, session_type="study", metadata.course_material_id)`. Returns conversation record.

### F-12.5 — Conversation Resolution

- **Functions in `storage.py`**: `save_conversation()`, `get_conversations_for_material()`, `get_messages_for_conversation()`, `search_conversations()`, `get_conversation_messages()`
- **Behavior**: Complete CRUD for conversations with message history. Conversations have `session_type` ("study" or "quickchat"), `metadata` (JSONB), and linked messages.

---

## 13. Observability & Monitoring

| ID | Feature | Source Files |
|---|---|---|
| F-13.1 | Langfuse Integration | `observability.py` |
| F-13.2 | Token Usage Tracking | `observability.py` |
| F-13.3 | Prompt Management (Langfuse) | All agents, `classifier.py` |
| F-13.4 | Trace Metadata | `observability.py` |

### F-13.1 — Langfuse Integration

- **Service**: `observability.py` (223 lines)
- **Behavior**: The central hub for all traces. Integrates with LangGraph and LangChain callback systems. Automatically exports traces to Langfuse Cloud.
- **Data Captured**: Latency, input/output tokens, model parameters, node execution order, tool results, parent-child relationships.

### F-13.2 — Token Usage Tracking

- **Behavior**: Each trace carries token counts for input and output. Used for cost monitoring (F-15.4).
- **Endpoint**: Langfuse Dashboard shows aggregated token costs by model and user.

### F-13.3 — Prompt Management (Langfuse)

- **Behavior**: All agent system prompts and tool descriptions are stored as "Prompts" in Langfuse. This allows updating prompts in the UI without redeploying backend code.
- **Fallback**: Each agent has a hardcoded fallback prompt to ensure system stays operational if Langfuse is down.
- **Loading**: `langfuse.get_prompt("prompt-name", type="chat")`

### F-13.4 — Trace Metadata

- **Behavior**: Every trace is enriched with:
  - `user_id`
  - `course_id` / `material_id`
  - `session_id`
  - `thread_id`
  - Agent personality settings
- **Why**: Allows filtering traces in Langfuse by specific user or course to debug issues.

---

## 14. Background Task Infrastructure

| ID | Feature | Source Files |
|---|---|---|
| F-14.1 | Material Processing Queue | `pdf_processor.py` |
| F-14.2 | Flashcard Task Management | `flashcard_task_service.py` |
| F-14.3 | Concurrency Control (Semaphore) | `pdf_processor.py` |
| F-14.4 | Real-time Status Polling | `endpoints.py`, `study.ts` |

### F-14.1 — Material Processing Queue

- **Behavior**: Uses FastAPI's `BackgroundTasks` to process PDFs asynchronously after upload. This prevents the HTTP request from timing out.
- **Status**: Tracked in `course_materials.status` ("pending", "processing", "completed", "failed").

### F-14.2 — Flashcard Task Management

- **Behavior**: Custom task service that runs long-running agentic generation in a background `asyncio` task. Maintains in-memory state for progress, cancellation, and results.
- **Persistence**: Unlike PDF processing, flashcard tasks carry rich progress metadata (F-3.9).

### F-14.3 — Concurrency Control (Semaphore)

- **Behavior**: Avoids overwhelming Gemini API / server resources during batch processing.
  - PDF processing: 5 concurrent pages
  - Snippet download: 10 concurrent requests
- **Implementation**: `asyncio.Semaphore(N)` wraps the parallel loops.

---

## 15. Infrastructure & Configuration

| ID | Feature | Source Files |
|---|---|---|
| F-15.1 | Supabase PostgreSQL | (infrastructure) |
| F-15.2 | Supabase Storage (Object Storage) | (infrastructure) |
| F-15.3 | Environment Configuration | `core/config.py` |
| F-15.4 | Cost Control / Quotas | (planned) |
| F-15.5 | Database Migrations | `backend/supabase/migrations/` |

### F-15.3 — Environment Configuration

- **Class**: `Settings` in `core/config.py` (Pydantic BaseSettings)
- **Behavior**: Validates all required environment variables on startup:
  - `SUPABASE_URL`, `SUPABASE_KEY`
  - `GOOGLE_API_KEY` (Gemini)
  - `GOOGLE_TTS_CREDENTIALS_JSON`
  - `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`
  - `ANKI_CONNECT_URL`
- **Profiles**: Supports `.env` local loading.

### F-15.5 — Database Migrations

- **Behavior**: SQL migration files for the Supabase schema. Defines all 15+ tables, RLS policies, and vector indexes.
- **Repository**: `backend/supabase/migrations/`




