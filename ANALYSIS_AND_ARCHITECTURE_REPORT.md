# StudyBuddy — Codebase Analysis & Target Architecture

> **Purpose**: Final architectural analysis and refactoring specification for **deployment, commercialization, and long-term development as a SaaS product**.

---

## 1. Executive Summary

StudyBuddy has reached a critical stage where its **agentic intelligence** (Tutor, Flashcard, and QuickChat agents) is highly effective, but its **underlying architecture** suffers from severe "God-File" patterns and direct coupling between infrastructure and business logic.

This report specifies the transition from a **monolithic storage-centric models** to a **Clean Architecture (Ports & Adapters)**.

### Current Key Stats
- **Total Features**: 106 (cataloged in `FEATURE_SPECIFICATION.md`)
- **Main God-File**: `storage.py` (89 functions, ~1,500 lines)
- **Agent God-File**: `tutor_agent.py` (~1,000 lines)
- **Primary Technical Debt**: Direct persistence coupling in agent nodes.

---

## 2. Core Problem Analysis (The "God-Files")

### 2.1 Storage.py (The Persistent Hub)
Current `storage.py` acts as:
1.  **Repository**: SQL queries for materials, analyses, courses.
2.  **Domain Service**: Anki deck renaming, material cleanup logic.
3.  **Task Manager**: Managing flashcard generation state.
4.  **Security Layer**: Ownership checks (`user_id` validation).

**Impact**: High risk of regression. Modification to a course-renaming feature can break the vector search embedding logic due to shared global state and shared helper functions.

### 2.2 Agent.py (The Monolithic Graphs)
The `TutorAgent` (LangGraph) handles:
1.  **State Management**: Resolving page context.
2.  **Prompt Engineering**: Heavy template injection.
3.  **Correction Logic**: Fixing Gemini tool call violations.

---

## 3. Target Commercial Architecture

To enable commercial scaling (SaaS), we move to **Layered Decoupling**.

### 3.1 Layer 1: Infrastructure (Adapters)
- **SupabaseAdapter**: Implements `MaterialRepository`, `CourseRepository`.
- **AnkiHeadlessAdapter**: Implements `AnkiGateway`.
- **GeminiAdapter**: Implements `LLMProvider`.

### 3.2 Layer 2: Domain Abstractions (Ports)
- Defined as Python **Protocols**.
- Agents *only* import these Protocols.
- Entities (Pydantic models) move to a central `domain/models.py`.

### 3.3 Layer 3: Application (Agents & Use Cases)
- **StudyService**: Orchestrates study session start.
- **FlashcardService**: Manages generation tasks.

---

## 4. Refactoring Roadmap (The 4 Phases)

### Phase 1: Entity Extraction & DbC setup
- Move all DB return types to `domain/models.py`.
- Define Python Protocols for every `storage.py` sub-domain.
- **Goal**: Zero direct `import storage` in `tutor_agent.py`.

### Phase 2: Repository Splitting
- Split `storage.py` into:
  - `course_repo.py`
  - `material_repo.py`
  - `analysis_repo.py`
- Wrap these in a `RepositoryRegistry`.

### Phase 3: Agent Dependency Inversion
- Inject repositories into Agent classes via `__init__`.
- Use FastAPI `Depends()` in `endpoints.py` to resolve concrete adapters.

### Phase 4: Observability and Scaling
- Enhance Langfuse tracking with cost-per-user metrics.
- Implement rate-limiting at the Redis adapter layer (Port: `RateLimiter`).

## 5. SOLID-Grounded Design Decisions

Our target design specifically addresses the criticisms of "lazy refactoring" by strictly applying SOLID principles:

1.  **Inverse Dependency on Storage**: Agents no longer know *how* a page analysis is stored (Supabase/Redis/JSON). They only know a `PageAnalysisReader` exists.
2.  **Tool Responsibility**: Tools like `SearchTopicTool` are extracted from agents. This satisfies **SRP** and allowing the search logic to be tested and optimized (F-5.4) without spinning up a full LangGraph state.
3.  **Interface Segregation**: The `AnkiGateway` protocol ensures that the `FlashcardAgent` doesn't have access to quiz deletion or message history, only to card synchronization.

---

## 6. Business Readiness & Commercialization

### 6.1 Multi-Tenancy (B-1.1)
- **Status**: Partially implemented via `user_id` filtering in all queries.
- **Requirement**: Move to Row-Level Security (RLS) policies at the database level to ensure cryptographic isolation between users.

### 6.2 Scalability (B-1.2)
- **Current**: Direct API calls to Gemini.
- **Requirement**: Implement a message queue (RabbitMQ/Redis) for PDF processing and flashcard generation to handle traffic spikes.

### 6.3 Performance (B-1.3)
- **Current**: Hybrid search is optimized via GIN indexes.
- **Requirement**: Cache frequent queries in Redis to bypass Postgres/Vector lookup for high-traffic topics.

---

## 7. Strategic Outlook

StudyBuddy has a unique competitive advantage in its **deep lecture integration** (Snippets + Multimodal Analysis). By adopting the **Ports & Adapters** architecture outlined in `SYSTEM_DESIGN.md`, the venture becomes:
- **Testable**: 100% unit test coverage of business logic without DB connections.
- **Flexible**: Easy to swap Gemini for local Llama-3 models or proprietary enterprise AI.
- **Commercial**: Ready for per-tenancy deployment and multi-region scaling.

---

## 8. Appendix: Refactoring Checklists

(Refer to `task.md` for live progress tracking of these architectural changes.)

