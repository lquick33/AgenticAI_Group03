# Project Title: Lernkompanien - Adaptive Learning Assistant

**Course:** Agentic Artificial Intelligence  
**Team Name:** Group 03

## Team Members

- Milan Elias Mayer (aesbit)
- Louis Braukmann (Louisbrau)

---

## 1. Executive Summary

University students face a critical challenge when studying complex lecture materials: navigating hundreds of PDF pages, understanding dense academic content, and maintaining consistent study habits. Traditional learning tools are passive and don't adapt to individual learning styles or provide context-aware guidance.

**StudyBuddy** addresses this problem through a multi-agent AI system that autonomously analyzes lecture slides, provides personalized tutoring, and generates study materials. Our solution employs four specialized agents orchestrated with LangGraph: a **TutorAgent** for interactive study sessions, a **QuickChatAgent** for topic discovery across courses, a **QuizGeneratorAgent** for comprehension testing, and a **FlashcardGeneratorAgent** for spaced repetition learning with Anki.

The system's key capability is **the seamless integration between agents and frontend, combined with orchestrated multi-agent collaboration and detailed knowledge integration**. Unlike using ChatGPT where users must manually copy-paste each page and provide context repeatedly, our agents work together autonomously: the **TutorAgent** guides the student through the lecture while it maintains conversation context across pages and automatically calls the **QuizGeneratorAgent** when topics are completed to check the students comprehension while being in the lecture, while the **FlashcardGeneratorAgent** incorporates both slide content and conversation history to create personalized flashcards, including snippets that the student can mark while being in our StudyReader. Each PDF page is pre-analyzed using Google Gemini 2.5 Flash (vision model) to extract structured knowledge (summaries, key terms, exam questions, diagram descriptions), which is stored in a database and seamlessly accessible to all agents. This enables **true detail depth** because agents access precise, page-specific information rather than processing entire documents at once.

This multi-agent approach offers significant advantages over generic chatbots: **dramatically improved speed** when working through materials (no manual copy-pasting of each page, no manual flashcard creation, no repeated context explanation), **genuine comprehension improvement** through the TutorAgent's context-aware explanations per slide while it also remembers previous messages and relations in a course topics, **direct knowledge reinforcement** through the QuizGeneratorAgent's adaptive testing that automatically triggers after topic completion, and **personalized study materials** through the FlashcardGeneratorAgent that incorporates both slide content and the student's specific questions and misunderstandings from the conversation. The system's proactivity and context-awareness transform passive reading into an interactive, guided learning experience where agents collaborate to support the student's learning journey, maintaining the depth and precision necessary for academic study while eliminating the tedious manual work required with traditional tools.

---

## 2. Introduction & Problem Statement

### Problem

University students encounter several interconnected challenges when studying lecture materials:

1. **Information Overload**: Students must navigate through hundreds of PDF pages across multiple courses, often struggling to find specific topics or understand how concepts relate.

2. **Lack of Personalized Guidance**: Traditional study methods don't adapt to individual learning styles, pace, or comprehension levels. Students may spend excessive time on topics they already understand or miss critical concepts. This is particularly challenging for **first-semester students** or those new to university studies, who often struggle with organization and maintaining an overview of their courses. These students may not understand content presented in lectures, lack the foundational knowledge to follow along, or work at a different pace than the lecture. Without personalized guidance that adapts to their knowledge level and learning pace, they risk falling behind or developing gaps in understanding that compound over time.

3. **Passive Learning**: Reading slides passively doesn't ensure comprehension. Students need interactive engagement, practice questions, and spaced repetition to master material. Many new students, especially those transitioning from high school to university, **don't know how to study effectively at the university level**. They may lack knowledge of effective learning strategies such as active recall, spaced repetition, or how to create meaningful study materials. Without guidance on proper study techniques, they resort to passive reading, which leads to poor retention and comprehension.

4. **Limitations of Current AI Solutions**: While students may attempt to use generic AI chatbots like Gemini or ChatGPT for studying, these tools have significant drawbacks. **Posting each page individually is extremely time-consuming**, requiring manual copy-pasting for every slide. The LLM **lacks context of the entire lecture**, making it difficult to understand how concepts connect across pages or how topics build upon each other. Alternatively, **uploading entire PDFs results in less detailed analysis** and loss of page-specific context, as the model cannot maintain focus on individual slides. Additionally, **creating flashcards requires manually copying each card from the chatbot**, which is highly repetitive and time-consuming, making it impractical for large lecture materials.

**Why existing solutions fail:**
- Traditional PDF readers lack context awareness of specific lecture content
- Generic chatbots (Gemini, ChatGPT) require manual page-by-page input or lose detail with full PDF uploads
- Generic chatbots cannot maintain lecture-wide context or understand relationships between pages
- Note-taking apps require manual effort to create study materials
- Static study tools don't adapt to individual learning progress
- Manual flashcard creation from chatbots is repetitive and time-consuming

**Why an agentic AI approach is necessary:**

Pure instruct Large Language Models (LLMs) like ChatGPT or Gemini are **not AI agents**—they lack the key agentic properties of **autonomy** and **proactivity**. While they exhibit social ability (communication) and reactivity (responding to inputs), they are better described as reactive, stateless, and passive tools. An agentic system, in contrast, provides:

1. **Deep Integration through Tools**: Agents enable deep integration both with the learning interface (frontend) and lecture content through specialized tools. Tools allow agents to:
   - Retrieve the complete context of an entire lecture (course material summary)
   - Access detailed, page-specific information including visual content (page analysis with diagrams)
   - Autonomously create quizzes when topics are completed
   - Generate flashcards incorporating conversation context and deciding what to include.
   - Search across multiple courses and materials

2. **Superior Context Management**: Unlike generic chatbots that lose context or require manual re-input, agents can manage context much more effectively through:
   - State persistence across a conversation session (LangGraph checkpointer)
   - Automatic context injection (current page, material ID, user ID) via StateAwareToolNode
   - Structured data access (pre-analyzed page content) rather than processing entire documents
   - Context-aware tool selection based on current state

3. **Autonomy (Agentic Property)**: Agents make **autonomous decisions** without constant human supervision:
   - Deciding when to call which tool based on user queries
   - Automatically creating quizzes when detecting topic completion
   - Choosing to skip or process pages during flashcard generation
   - Adapting explanations based on conversation history

4. **Proactivity (Agentic Property)**: Agents exhibit **goal-directed behavior** and take initiative:
   - Proactively explaining new slides when user navigates to a new page
   - Automatically generating quizzes after topic completion (without user request)
   - Suggesting related topics or pages during searches
   - Asking comprehension-check questions to ensure understanding

Non-agentic approaches (simple RAG, static chatbots, rule-based systems) cannot provide this level of autonomy, proactivity, and context-aware decision-making. The agentic paradigm enables the system to act as an intelligent tutor that understands both content and student needs, going beyond reactive text generation to proactive, goal-directed assistance.

### Objectives

Our agent system must successfully achieve:

1. **Multimodal Content Analysis**: Analyze lecture slides (PDF pages) using Google Gemini vision model with structured output (Pydantic schema) to extract per-page information: summary, key terms, exactly 2 exam questions, and diagram descriptions. The structured output ensures consistent data format and enables reliable downstream processing by agents.

2. **Context-Aware Tutoring**: Provide explanations and answer questions about lecture content with reference to the current page. The TutorAgent maintains full conversation context across sessions using LangGraph checkpointer, loads conversation history from Supabase, and proactively explains new slides when users navigate to different pages. The agent has access to course material summaries and page-specific analyses includeing access to images of the slides through specialized tools.

3. **Proactive Quiz Generation**: Automatically generate 3-5 comprehension questions (up to 8 for complex topics) when the TutorAgent detects a subtopic completion. Questions follow a difficulty distribution: 1-2 easy questions (basic understanding), 1 medium question (application), and at least 1 hard question (deep understanding, analysis). Each question includes 4 multiple-choice options and an explanation.

4. **Flashcard Generation**: Generate 1-4 Anki-compatible flashcards per page based on content complexity, incorporating both slide content (from page analyses) and conversation context (from chat history). The system implements course-wide deduplication using a two-phase approach: hash-based exact matching (O(1)) and fuzzy similarity matching (threshold 0.85) against existing Anki cards to prevent redundant cards.

5. **Topic Discovery**: Enable students to search for topics across all their courses and materials using the QuickChatAgent. The search tool presents matching pages with context (summary, key terms, relevance scores) and **automatically controls the frontend** to open materials: in discovery mode, the agent sends an `open_material` Server-Sent Event (SSE) that immediately opens the PDF viewer at the relevant page; in tutoring mode (when a PDF is already open), the agent sends a `pending_navigation` event and asks for user confirmation before navigating. This bidirectional communication between agent and frontend enables seamless navigation without manual page selection.

6. **Personalization**: Adapt communication style and behavior based on user preferences stored in the `user_preferences` table: language (German/English), personality traits (formality, humor, encouragement), learning style (linear/iterative), and agent persona (strict/humorous/buddy). These preferences are dynamically loaded and compiled into agent system prompts at runtime.

### Scope

**What the system does:**
- Analyzes PDF lecture slides using Google Gemini vision model with structured output (Pydantic schemas)
- Provides interactive tutoring during study sessions with conversation persistence via LangGraph checkpointer
- Proactively explains new slides when users navigate to different pages
- Generates quizzes and flashcards automatically based on learning progress and topic completion
- Searches topics across multiple courses and materials with relevance scoring
- Maintains conversation history and learning progress in Supabase
- Integrates with Anki for flashcard synchronization via AnkiConnect with course-wide deduplication

**What the system does NOT do:**
- Calendar management and scheduling (planned but not implemented in this version)
- Video or audio content analysis (only PDF/image-based content)
- Automatic grading of assignments or exams
- Integration with ANKI is given but no real agentic features are completely implemented as of now due to time constraints.

---

## 3. System Architecture

### High-Level Architecture

The system follows a **multi-agent architecture** with four specialized agents orchestrated using LangGraph state machines:

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Study Reader  │  │ Quick Chat    │  │ Dashboard    │     │
│  │ (PDF Viewer)  │  │ (Topic Search)│  │ (Progress)   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │ HTTP/SSE
          ┌──────────────────▼──────────────────┐
          │      FastAPI Backend (Python)        │
          │  ┌────────────────────────────────┐ │
          │  │     API Endpoints               │ │
          │  │  - /api/chat/initiate          │ │
          │  │  - /api/chat/message            │ │
          │  │  - /api/flashcards/generate     │ │
          │  └──────────────┬─────────────────┘ │
          │                  │                   │
          │  ┌──────────────▼─────────────────┐ │
          │  │   LangGraph State Machines     │ │
          │  │   (BaseAgent Pattern)          │ │
          │  └──────────────┬─────────────────┘ │
          │                  │                   │
          │  ┌──────────────▼─────────────────┐ │
          │  │   Four Specialized Agents      │ │
          │  │   1. TutorAgent                 │ │
          │  │   2. QuickChatAgent             │ │
          │  │   3. QuizGeneratorAgent         │ │
          │  │   4. FlashcardGeneratorAgent    │ │
          │  └──────────────┬─────────────────┘ │
          │                  │                   │
          │  ┌──────────────▼─────────────────┐ │
          │  │   Tools Layer (LangChain)      │ │
          │  │   - get_page_analysis          │ │
          │  │   - search_topic                │ │
          │  │   - create_quiz                 │ │
          │  │   - get_course_material_summary │ │
          │  └──────────────┬─────────────────┘ │
          └─────────────────┼───────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │      Supabase (PostgreSQL)         │
          │  - page_analyses (JSONB)          │
          │  - conversations, messages         │
          │  - quizzes, flashcards              │
          │  - user_preferences                 │
          └───────────────────────────────────┘
```

### LangGraph Architecture

All agents inherit from `BaseAgent` and implement LangGraph state machines with the following pattern:

**BaseAgent Abstract Class:**
```python
class BaseAgent(ABC):
    def __init__(self, llm, name, system_prompt, checkpointer, store):
        self.llm = llm
        self.checkpointer = checkpointer  # For conversation persistence
        self.store = store  # For long-term memory (optional)
        self._build_graph()  # Abstract method
    
    @abstractmethod
    def _build_graph(self) -> None:
        """Build the LangGraph workflow."""
        pass
```

#### 3.2.1. TutorAgent

The TutorAgent is the primary interface for student interactions, responsible for explaining content, answering questions, and providing context-aware guidance.

**TutorAgent Graph Structure:**
```
START
  ↓
agent (call_model)
  ↓
should_continue (conditional)
  ├─→ tools (StateAwareToolNode) → agent (loop)
  └─→ END
```


The TutorAgent demonstrates **"elegant simplicity"** in graph design: the graph structure is minimal (only 2 nodes + 1 conditional edge), but the complexity is **distributed across multiple layers**:

1. **System Prompt (Langfuse-managed)**: Contains all behavioral instructions:
   - Proactive explanations when users navigate to new pages
   - Quiz suggestions when topics are completed
   - Context-aware tutoring based on conversation history
   - Personalization (language, formality, humor, encouragement)
   - Tool usage guidelines and state injection hints

2. **`call_model` Node (Complex Logic)**: Despite being a single node, this function contains ~330 lines of sophisticated logic:
   - **Message History Management**: Sliding window truncation (last 10 messages) with tool-call pair preservation
   - **Dynamic Context Injection**: Builds context from state (`current_page`, `material_id`, `course_material_summary`) and enhances system prompt
   - **Message Ordering Validation**: `_fix_incomplete_tool_calls()` ensures Gemini API compliance (AIMessage with tool_calls must follow HumanMessage/ToolMessage)
   - **Multimodal Tool Response Handling**: Converts image data from `get_page_image` tool into multimodal content format
   - **Observability**: Langfuse callback handler integration for tracing
   - **State-Aware Prompt Enhancement**: Injects current state values into system prompt so LLM knows available context

3. **Tools Layer (External Complexity)**: The four tools (`get_page_analysis`, `get_course_material_summary`, `create_quiz`, `get_page_image`) contain their own complex logic:
   - Database queries with JSONB operations
   - Agent orchestration (e.g., `create_quiz` triggers `QuizGeneratorAgent`)
   - Image URL generation from Supabase Storage

4. **StateAwareToolNode (Automatic State Injection)**: Prevents LLM hallucination by automatically filling tool parameters from state:
   - `material_id` → `course_material_id`
   - `current_page` → `page_number` (if not explicitly provided)
   - `user_id` → `user_id`

5. **LLM Autonomy**: The LLM decides autonomously which tools to call and when, based on the comprehensive system prompt. This eliminates the need for explicit routing nodes (e.g., "explain_page_node", "answer_question_node", "suggest_quiz_node")—the LLM handles all these behaviors through tool selection.

**Result**: A simple graph structure that is easy to understand and maintain, while supporting complex behaviors through intelligent prompt engineering, sophisticated node logic, and autonomous LLM decision-making.

**Nodes:**
1. **`call_model`**: 
   - Calls LLM with tools bound (`llm.bind_tools(tools)`)
   - Truncates message history to last 10 messages (sliding window)
   - Injects state context (`current_page`, `material_id`, `user_id`) into system prompt
   - Handles Gemini API message order requirements
   - Processes multimodal tool responses (images)

2. **`tools`** (StateAwareToolNode):
   - Executes tool calls from LLM
   - **Automatically injects state values** (`material_id` → `course_material_id`, `current_page` → `page_number`, `user_id`)
   - Prevents LLM from hallucinating incorrect IDs
   - Returns ToolMessages with results

3. **`should_continue`** (conditional edge):
   - Checks if last message has `tool_calls`
   - Routes to `tools` if tools called, else `END`
   - Special handling: After `create_quiz` tool call, graph ends (quiz is displayed to user)

**State Schema:**
```python
class TutorState(MessagesState):
    """Extends MessagesState for automatic message handling."""
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict] = None
    # messages: List[BaseMessage] inherited from MessagesState
```

**TutorAgent Data Flow Example:**

**Scenario: User asks "What is a sequence diagram?" on page 15**

1. **Frontend** → Sends HTTP POST to `/api/chat/message` with:
   ```json
   {
     "message": "What is a sequence diagram?",
     "material_id": "mat-123",
     "page_number": 15,
     "user_id": "user-456",
     "thread_id": "conv-789"
   }
   ```

2. **FastAPI Endpoint** → Initializes TutorAgent with state:
   ```python
   state = TutorState(
       current_page=15,
       material_id="mat-123",
       user_id="user-456"
   )
   ```

3. **TutorAgent.call_model()** → 
   - Loads conversation history from checkpointer (thread_id="conv-789")
   - Truncates to last 10 messages
   - Enhances system prompt with state: "Current page: 15, Material: mat-123"
   - Calls LLM with tools bound

4. **LLM Decision** → Decides to call `get_page_analysis` tool

5. **StateAwareToolNode** → 
   - Receives tool call: `get_page_analysis(course_material_id="test-id", page_number=15)`
   - **Automatically injects**: `course_material_id="mat-123"` (from state.material_id)
   - Executes tool with correct IDs

6. **Tool Execution** → Queries Supabase:
   ```sql
   SELECT analysis_data FROM page_analyses 
   WHERE course_material_id = 'mat-123' AND page_number = 15
   ```
   Returns: `{summary: "...", key_terms: ["sequence diagram", "UML"], ...}`

7. **TutorAgent.call_model()** (next iteration) →
   - Receives ToolMessage with page analysis
   - Generates explanation: "A sequence diagram is a UML diagram that shows..."
   - No more tool calls → Graph ends

8. **Response** → Streamed back to frontend via SSE, displayed in chat

#### 3.2.2. QuickChatAgent

The QuickChatAgent is a specialized agent for global search and navigation, operating in two distinct modes: **Discovery** (searching across courses) and **Tutoring** (teaching specific content).

**QuickChatAgent Graph Structure:**
```
START
  ↓
agent (call_model)
  ↓
should_continue (conditional)
  ├─→ tools (StateAwareToolNode) → agent (loop)
  └─→ END
```

**Key Features:**

1. **Dual-Mode Operation**:
   - **Discovery Mode**: Uses `search_topic` and `get_user_courses` tools to find content across the entire knowledge base. The agent can control the frontend via Server-Sent Events (SSE) to automatically navigate users to relevant pages by emitting `open_material` events.
   - **Tutoring Mode**: Once a page is selected, it behaves like the TutorAgent, using `get_page_analysis`, `get_course_material_summary`, `create_quiz`, and `get_page_image` tools. It sends `pending_navigation` events to ask for user confirmation before switching context to a different page.

2. **Frontend Control via SSE**: The agent has a unique capability to "drive" the frontend application. By emitting specific events in the SSE stream (`open_material` for automatic navigation in discovery mode, `pending_navigation` for confirmation-required navigation in tutoring mode), it can trigger client-side navigation (opening PDF viewers, switching pages).

3. **Enhanced Context Window**: Uses a slightly larger sliding window (15 messages) than the TutorAgent (10 messages) to maintain broader search context during discovery operations.

4. **State-Aware Tool Injection**: Similar to TutorAgent, uses a custom `StateAwareToolNode` that automatically injects state values (`user_id`, `material_id`, `current_page`) into tool calls to prevent LLM hallucination of incorrect IDs.

**State Schema:**
```python
class QuickChatState(State):
    mode: str = "discovery"  # "discovery" | "tutoring"
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict] = None
    navigation_request: Optional[Dict[str, Any]] = None
```

**Nodes:**
1. **`call_model`**: 
   - Calls LLM with tools bound (`llm.bind_tools(tools)`)
   - Truncates message history to last 15 messages (sliding window)
   - Builds enhanced system prompt with current state context (mode, material_id, current_page, course_id, summary)
   - Handles Gemini API message order requirements

2. **`tools`** (StateAwareToolNode):
   - Executes tool calls from LLM
   - **Automatically injects state values** (`user_id`, `material_id` → `course_material_id`, `current_page` → `page_number`)
   - Prevents LLM from hallucinating incorrect IDs
   - Returns ToolMessages with results

3. **`should_continue`** (conditional edge):
   - Checks if last message has `tool_calls`
   - Routes to `tools` if tools called, else `END`

**QuickChatAgent Data Flow Example:**

**Scenario: User asks "Where is polymorphism explained?" in discovery mode**

1. **Frontend** → Sends HTTP POST to `/api/quickchat/message` with:
   ```json
   {
     "message": "Where is polymorphism explained?",
     "user_id": "user-456",
     "thread_id": "quickchat-123"
   }
   ```

2. **FastAPI Endpoint** → Initializes QuickChatAgent with state:
   ```python
   state = QuickChatState(
       mode="discovery",
       user_id="user-456"
   )
   ```

3. **QuickChatAgent.call_model()** → 
   - Loads conversation history from checkpointer
   - Truncates to last 15 messages
   - Enhances system prompt: "Mode: Discovery (searching for topics)"
   - Calls LLM with tools bound

4. **LLM Decision** → Decides to call `search_topic` tool

5. **StateAwareToolNode** → 
   - Receives tool call: `search_topic(query="polymorphism", user_id="test-id")`
   - **Automatically injects**: `user_id="user-456"` (from state)
   - Executes tool with correct user_id

6. **Tool Execution** → `SearchTopicTool._run()` executes hybrid search:
   - **Keyword Extraction**: LLM extracts keywords → `["Polymorphismus", "polymorphism", "Vererbung", "OOP"]`
   - **Vector Search**: Calls `search_pages_by_embedding()` RPC with query embedding (pgvector HNSW)
   - **Keyword Search**: Full-text search on `page_analyses.analysis_data` JSONB
   - **RRF Fusion**: Combines results with Reciprocal Rank Fusion (K=60, 60% vector + 40% keyword weight)
   - **Best intro page selection** (`_pick_best_intro_page()`): finds where the topic is *introduced*, not just mentioned.
     - **Phase 1 (optional, when LLM available)**: LLM picks best intro from top 15 candidates using Langfuse prompt `search-topic/intro-page-pick` (or fallback). Prefers section/chapter title slides, first page of a block, and pages whose title/summary clearly introduces the concept. If LLM returns a valid page, that is used.
     - **Phase 2 (heuristic, when no LLM or LLM fails)**: (1) **Fast path**: If any result has `is_chapter_heading`, score by title match (with cross-language DE↔EN and focus factor for short titles); among similar scores, prefer earliest page. (2) **Aggregate scoring**: title (48%) + primary key_terms (16%) + continuity (24%) + semantic (8%) + material (18%), plus synergy bonus (title + material name match) and chapter-heading bonus. Continuity = avg correlation-to-query of the *next 6 pages* from DB (section start detection). (3) **First-of-block / earlier-block bonuses**: First page of adjacent-page blocks gets bonus (scales with block length); earlier blocks get +0.10, +0.05, etc. (4) **Tie-breaking**: Within top score band, prefer earliest chapter heading, then earliest first-of-block, then earliest page.
   - Returns: `{found: true, results: [...], recommended_page: 42}` with best intro page first

7. **QuickChatAgent.call_model()** (next iteration) →
   - Receives ToolMessage with search results
   - Generates response: "I found polymorphism explained on page 42 in 'Object-Oriented Programming'..."
   - Emits SSE event: `open_material(material_id="mat-789", page_number=42)` → Frontend automatically opens PDF viewer
   - No more tool calls → Graph ends

8. **Response** → Streamed back to frontend via SSE, displayed in chat, PDF viewer opens automatically

#### 3.2.3. QuizGeneratorAgent

The QuizGeneratorAgent is a specialized sub-agent invoked by the TutorAgent to create assessment material. It focuses on generating valid, structured assessment content rather than conversation.

**QuizGeneratorAgent Graph Structure:**
```
START
  ↓
generate (generate_node)
  ↓
END
```

**Key Features:**

1. **Linear Execution**: Unlike the conversational agents, this graph is linear (`START → generate → END`) because it performs a specific task without user interaction loops. It's invoked programmatically by the TutorAgent when a subtopic is completed.

2. **Structured Output Guarantee**: Uses `llm.with_structured_output(QuizData)` to enforce strict Pydantic schema validation for generated quizzes, ensuring the frontend always receives valid JSON that matches the `QuizData` schema.

3. **Strict Validation Logic**: The `generate_node` implements rigorous post-generation validation:
   - **Question count check**: 3-8 questions (minimum 3, maximum 8)
   - **Difficulty distribution check**: 
     - At least 1 easy question (1-2 preferred)
     - At least 1 medium question
     - At least 1 hard question
   - **Option count check**: Exactly 4 options per question (A, B, C, D)
   - **Logic check**: Correct answer must be present in the options list
   - **Explanation check**: Each question must have a non-empty explanation

4. **Context Building**: Builds context from `page_analyses` (summary, key terms) for the specified page range (`start_page` to `end_page`), allowing focused quiz generation for specific topics.

5. **Error Handling**: Uses custom exceptions (`QuizStateError`, `QuizValidationError`, `QuizDataError`, `QuizGenerationError`) for precise error reporting and debugging.

**State Schema:**
```python
class QuizGeneratorState(MessagesState):
    page_analyses: List[Dict[str, Any]]  # Input context (required)
    topic: str                           # Quiz topic (required)
    start_page: int                      # Page range start (required)
    end_page: int                        # Page range end (required)
    course_material_id: Optional[str]    # For tracing
    user_id: Optional[str]               # For tracing
    quiz_data: Optional[QuizData]        # Output (Pydantic model)
```

**Nodes:**
1. **`generate_node`**: 
   - Validates required state fields (`page_analyses`, `topic`, `start_page`, `end_page`)
   - Builds context from page analyses (summary, key terms for each page)
   - Creates prompt for quiz generation with topic and page range
   - Calls structured LLM (`llm.with_structured_output(QuizData)`) to ensure valid JSON output
   - Validates generated quiz using `_validate_quiz()` (question count, difficulty distribution, format)
   - Returns state with `quiz_data` field populated

**LLM Call Pattern:**
- **Single structured LLM call** per quiz generation:
  - Uses `llm.with_structured_output(QuizData)` to guarantee Pydantic-compliant output
  - Prompt includes context from all pages in the range
  - Result is validated against strict requirements before returning

**QuizGeneratorAgent Data Flow Example:**

**Scenario: TutorAgent suggests quiz after completing "Sequence Diagrams" topic (pages 15-20)**

1. **TutorAgent** → Calls `create_quiz` tool with:
   ```python
   {
       "topic": "Sequence Diagrams",
       "start_page": 15,
       "end_page": 20,
       "course_material_id": "mat-123",
       "user_id": "user-456"
   }
   ```

2. **CreateQuizTool** → Invokes `QuizGeneratorAgent.generate_quiz()`:
   - Fetches page analyses for range 15-20 from database
   - Prepares initial state with page analyses and topic

3. **QuizGeneratorAgent.generate_node()** → 
   - Validates state (checks page_analyses, topic, page range)
   - Builds context: "Seite 15: Zusammenfassung: ..., Seite 16: ..."
   - Creates prompt: "Erstelle ein Quiz für das folgende Thema: Sequence Diagrams..."
   - Calls structured LLM: `structured_llm.invoke(messages)`

4. **Structured LLM** → Returns `QuizData` object directly (Pydantic-validated):
   ```python
   QuizData(
       questions=[
           QuizQuestion(id="q1", difficulty="easy", ...),
           QuizQuestion(id="q2", difficulty="medium", ...),
           QuizQuestion(id="q3", difficulty="hard", ...),
           ...
       ]
   )
   ```

5. **Validation** → `_validate_quiz()` checks:
   - Question count: 3-8 ✓
   - Difficulty: 1 easy, 1 medium, 1+ hard ✓
   - Each question: 4 options, correct_answer in options, explanation present ✓

6. **Result** → Returns `QuizData` to TutorAgent → Tool returns to user → Frontend displays quiz

#### 3.2.4. FlashcardGeneratorAgent

The FlashcardGeneratorAgent generates Anki-compatible flashcards from lecture materials. Unlike the TutorAgent's simple graph, this agent uses a more complex state machine to handle page-by-page processing with resumability.

**FlashcardGeneratorAgent Graph Structure:**
```
START
  ↓
initialize_node (load page_analyses, snippets)
  ↓
classify_node (material classification + parallel skip decisions)
  ↓
check_more_pages (conditional)
  ├─→ continue: process_page_node
  │     ↓
  │   skip_decision_node (uses pre-evaluated decision or LLM fallback)
  │     ↓ (conditional)
  │   ├─→ skip: update_progress_node → check_more_pages
  │   └─→ generate: get_context_node
  │         ↓
  │       generate_cards_node (LLM generates 1-2 cards)
  │         ↓
  │       update_progress_node → check_more_pages
  └─→ done: save_cards_node → END
```

**Key Features:**

1. **Parallel Skip Decision Evaluation**: The `classify_node` evaluates skip decisions for all pages in parallel using `ThreadPoolExecutor`, optimizing performance for large materials.

2. **Resumability**: The graph uses LangGraph checkpointer to enable resumability. If generation fails at page 50/100, it can resume from checkpoint using the same `thread_id`, avoiding redundant processing.

3. **Context-Aware Generation**: The `get_context_node` retrieves:
   - Page analysis (summary, key terms, exam questions)
   - Conversation snippets (relevant chat history)
   - Course material summary (overall context)

4. **Deduplication**: Generated flashcards are checked against existing Anki cards using hash-based exact matching and fuzzy similarity (threshold 0.85) to prevent duplicates.

**State Schema:**
```python
class FlashcardState(TypedDict):
    material_id: str
    user_id: str
    current_page: int
    total_pages: int
    page_analyses: List[dict]  # Loaded in initialize_node
    snippets: List[dict]  # Conversation snippets
    skip_decisions: Dict[int, bool]  # Pre-evaluated skip decisions
    generated_cards: List[dict]  # Accumulated flashcards
    progress: Dict[str, Any]  # Generation progress
```

**Nodes:**
1. **`initialize_node`**: Loads all page analyses and conversation snippets from database
2. **`classify_node`**: Classifies material type and evaluates skip decisions for all pages in parallel
3. **`process_page_node`**: Processes a single page (retrieves skip decision or generates cards)
4. **`skip_decision_node`**: Uses pre-evaluated decision or falls back to LLM call
5. **`get_context_node`**: Retrieves relevant context (page analysis, snippets, course summary)
6. **`generate_cards_node`**: LLM generates 1-2 flashcards based on page content and context
7. **`update_progress_node`**: Updates progress and moves to next page
8. **`save_cards_node`**: Saves all generated flashcards to database and Anki

**LLM Call Pattern:**
- **Two calls per page** (observed in Langfuse):
  1. **Skip decision call**: Either pre-computed in parallel during `classify_node` or as fallback in `skip_decision_node`
  2. **Card generation call**: In `generate_cards_node` for pages that are not skipped

This pattern ensures efficient processing while maintaining quality through context-aware generation.

---

## 4. Implementation Details

### 4.1. LLM Selection & Configuration

**Models Used:**

**Google Gemini 2.5 Flash** (single model for all tasks)
   - Primary model used throughout the system
   **Use Cases:**
   - **Agent Conversations**: TutorAgent, QuizGeneratorAgent, FlashcardGeneratorAgent, QuickChatAgent
   - **Multimodal Analysis**: PDF page analysis during upload (extracts structured information from slide images)
   - **Note**: The same model instance is used for both conversational and vision tasks, leveraging Gemini's native multimodal capabilities.

**Justification for Google Gemini 2.5 Flash:**

Our selection of Google Gemini 2.5 Flash as the sole foundational LLM for StudyBuddy is based on its superior multimodal capabilities, performance characteristics, and seamless integration benefits, directly addressing our project's core requirements:

- **Unified Multimodal Intelligence**: Gemini 2.5 Flash natively supports both advanced conversational understanding and powerful vision analysis. This allows us to use a single model instance for all tasks—from generating dynamic tutor responses and crafting intelligent quizzes to extracting structured insights from complex lecture slide images during PDF analysis. This unified approach simplifies our architecture, reduces API overhead, and ensures consistent AI behavior across the entire learning ecosystem.

- **Optimized Performance & Responsiveness**: The model consistently delivers excellent reasoning for tool-calling and reliable structured output generation, which is critical for agent accuracy. Furthermore, its significantly lower average latency (approximately 500ms) compared to alternatives like GPT-4 (2-3s) is crucial for maintaining real-time, fluid interactions within study sessions, where users expect immediate responses.

- **Strategic Context Management**: While Gemini 2.5 Flash offers an impressive 1M token context window, our system strategically employs a sliding window approach for conversational history (keeping the last 10 messages in the TutorAgent). This design decision effectively prevents token explosion during extended study sessions, ensuring cost-efficiency and consistent processing speed, while the complete conversation history is robustly preserved within the LangGraph state for full resumability. The large context window is intentionally preserved for future features, such as comprehensive cross-lecture analysis to identify relationships and patterns across multiple course materials, enabling deeper insights into interconnected topics.

- **Unified Provider Strategy**: We deliberately chose to use Google Gemini exclusively across all system components, rather than mixing providers (e.g., OpenAI for conversations, Gemini for vision). This "all-in-one" approach simplifies architecture, reduces API management complexity, and ensures consistent behavior. It also enables seamless future enhancements, such as leveraging Nano Banana Pro for advanced diagram explanations and visual content analysis, without introducing provider-specific compatibility challenges.

- **Cost-Effectiveness & Accessibility**: The Gemini API proves to be highly cost-effective across its diverse use cases. Its ready availability and straightforward setup further streamline development and deployment, removing barriers associated with complex multi-provider configurations and ensuring operational simplicity.

**Hyperparameters:**

- **Temperature**: `0.1` for all agents (set in `get_gemini_model()` function)
  - Rationale: Lower temperature ensures consistent tool-calling and structured output. We want reliable, deterministic behavior rather than creative variation. Based on our development experience, lower temperature values significantly improve tool-calling reliability and structured output consistency.

- **Top-p**: Not explicitly set (uses model defaults)
- **Max Tokens**: Not set (allows full responses, important for detailed explanations)
- **Response Format**: Structured output via `llm.with_structured_output(PydanticModel)` is used for:
  - **QuizGeneratorAgent**: `QuizData` model for quiz generation
  - **FlashcardGeneratorAgent**: `FlashcardGenerationResult` for card generation, `PageSkipDecision` for skip decisions, and `MaterialClassification` for material classification
  - This guarantees valid JSON output and eliminates parsing errors

### 4.2. Key Components (Memory, Tools)

**Tools:**

1. **`get_page_analysis(course_material_id: str, page_number: int, user_id: str) -> dict`**
   - Fetches structured analysis data from `page_analyses` table (JSONB column)
   - Returns: `{summary: str, key_terms: List[str], exam_questions: List[str], diagram_description: Optional[str]}`
   - Used by: TutorAgent, QuickChatAgent
   - Implementation: Direct Supabase query, no RAG/vector search

2. **`get_course_material_summary(course_material_id: str, user_id: str) -> dict`**
   - Retrieves global course overview with all topics and page ranges
   - Used by: TutorAgent for context-aware responses across topics
   - Returns: `{title: str, topics: List[dict], total_pages: int}`

3. **`create_quiz(start_page: int, end_page: int, course_material_id: str, user_id: str) -> dict`**
   - Triggers QuizGeneratorAgent to create comprehension quiz
   - Internally: Loads page analyses for range, calls QuizGeneratorAgent.generate_node()
   - Returns: `{quiz_id: str, quiz_data: QuizData}`
   - Used by: TutorAgent when subtopic completed

4. **`search_topic(query: str, user_id: str) -> List[dict]`**
   - Searches for topics across all user's courses and materials using RAG
   - Implementation: Hybrid search (vector + keyword via RRF fusion) with fallback to multi-keyword search
   - **Best intro page selection**: `_pick_best_intro_page()` finds where topics are *introduced* (best page to start revising). When LLM is available: LLM picks from top 15 candidates (Langfuse prompt or fallback). Otherwise heuristic: chapter headings (prioritized, prefer earliest page); aggregate scoring (title 48%, key_terms 16%, continuity 24%, semantic 8%, material 18% plus synergy/chapter bonuses); continuity = avg correlation of *next 6 pages* from DB; first-of-block and earlier-block bonuses; tie-break to earliest page in top band.
   - Returns: `[{material_id, page_number, summary, key_terms, relevance_score, ...}]`
   - Used by: QuickChatAgent in discovery mode

5. **`get_user_courses(user_id: str) -> List[dict]`**
   - Lists all courses and materials for a user
   - Returns: `[{course_id, course_name, materials: [{material_id, title, ...}]}]`
   - Used by: QuickChatAgent

6. **`get_page_image(course_material_id: str, page_number: int, user_id: str) -> str`**
   - Returns public URL for page image from Supabase Storage
   - Used by: TutorAgent for visual context in explanations

**Memory:**

We use a **hybrid persistence strategy** combining LangGraph Checkpointer with Supabase database storage to achieve both performance and long-term persistence:

**1. LangGraph Checkpointer (Short-term State Management):**

- **Thread-based Persistence**: Each conversation session has a unique `thread_id` (typically `conversation_id` from database for TutorAgent, or generated for other agents)
- **Checkpointer Types** (varies by agent):
  - **TutorAgent & QuickChatAgent**: Use `MemorySaver` (in-memory dictionary) for fast state access during active sessions
  - **FlashcardGeneratorAgent**: Uses `PostgresSaver` (persists to Supabase PostgreSQL) with automatic fallback to `MemorySaver` if database unavailable
  - **QuizGeneratorAgent**: Uses `MemorySaver` (optional, typically created per-request without persistence)
- **State Persistence**: Agent state (`current_page`, `material_id`, `messages`, etc.) is automatically checkpointed after each node execution
- **Performance Rationale**: MemorySaver provides sub-millisecond state access (~0.01ms) compared to PostgresSaver (~20-100ms per checkpoint). Since LangGraph checkpoints state after every node execution (typically 3-5 checkpoints per user message), using MemorySaver saves 60-500ms latency per request, crucial for real-time conversational interactions.

**2. Supabase Database (Long-term Message Persistence):**

- **Dual Storage Strategy**: While MemorySaver handles fast state access during sessions, user and assistant messages are simultaneously persisted to Supabase `messages` table for long-term storage. **Note**: ToolMessages are only stored in MemorySaver and are lost on backend restart.
- **Restart Recovery**: When the backend restarts, MemorySaver is empty, but the system automatically loads user and assistant messages from Supabase and bootstraps them back into the LangGraph state, enabling conversation continuation. ToolMessages from previous sessions are not recovered.
- **Why Not PostgresSaver for All Agents?**: 
  - **Performance**: PostgresSaver adds 20-100ms latency per checkpoint (4+ checkpoints per request = 80-400ms overhead)
  - **Redundancy**: User and assistant messages are already captured in Supabase `messages` table, making PostgresSaver redundant for conversational agents
  - **Optimal Balance**: MemorySaver provides fast in-session access, while Supabase Messages ensure persistence across restarts—best of both worlds

**3. Message History & State Management:**

- **Message History**: 
  - **HumanMessage & AIMessage**: Stored in both MemorySaver (for fast access) and Supabase `messages` table (for persistence)
  - **ToolMessage**: Only stored in MemorySaver (not persisted to database). These messages are lost on backend restart, but this is acceptable since tool results are typically ephemeral and the conversation flow can continue without them.
- **State Recovery**: On backend restart, `load_conversation_with_messages()` retrieves user and assistant messages from Supabase and converts them back to LangGraph Message objects (HumanMessage, AIMessage, SystemMessage). ToolMessages are not restored, but the conversation can continue normally as the LLM can make new tool calls if needed.
- **Sliding Window** (conversational agents only):
  - **TutorAgent**: Keeps last 10 messages in context (`MAX_HISTORY_MESSAGES = 10`) to prevent token explosion while maintaining conversation flow
  - **QuickChatAgent**: Keeps last 15 messages (`MAX_HISTORY_MESSAGES = 15`) for additional search context
  - **QuizGeneratorAgent & FlashcardGeneratorAgent**: No sliding window (not conversational agents, process material in batches)


### 4.3. Prompt Engineering

**System Prompts Overview:**

All system prompts are managed in **Langfuse** and loaded at runtime. Prompts use variables (e.g., `{{formality_text}}`) that are compiled at runtime. If Langfuse is unavailable, agents either raise a RuntimeError or use hardcoded fallback prompts (agent-specific).

#### 1. TutorAgent System Prompt

**Langfuse Name**: `tutor-agent/system-prompt-{language}`
- **German (DE)**: Version 12 (production)
- **English (EN)**: Version 3 (production)
- **Type**: Chat prompt
- **Variables**: `{{formality_text}}`, `{{humor_text}}`, `{{encouragement_text}}`
- **Fallback**: RuntimeError if Langfuse unavailable (no hardcoded fallback)

**Key Structure** (simplified - actual prompt is ~2000 characters):

```
Du bist ein persönlicher Tutor für Universitätsstudenten.

## Deine Rolle
- Erkläre auf studentenfreundlichem Niveau (nicht zu akademisch, nicht zu einfach)
- Verwende Analogien und zerlege komplexe Konzepte in verständliche Schritte
- Verknüpfe thematisch mehrere Inhalte der Vorlesung

## Kontext
- Aktuelle Seite: {current_page} (automatisch injiziert)
- Material-ID: {material_id} (automatisch injiziert)
- Benutzer-ID: {user_id} (automatisch injiziert)

## Tools
- get_page_analysis: Hole die strukturierte Analyse für die aktuelle Seite
  → WICHTIG: course_material_id und page_number werden AUTOMATISCH injiziert
- get_course_material_summary: Gesamtübersicht der Vorlesung
- get_page_image: Hole visuellen Snapshot einer Seite als Bild (für komplexe Diagramme/Charts)
  → WICHTIG: course_material_id, page_number und user_id werden AUTOMATISCH injiziert
- create_quiz: Erstelle Quiz für abgeschlossene Themen (KRITISCH: Tool muss aufgerufen werden)

## Persönlichkeit (Variablen)
{{formality_text}}  # "formal" | "informal" | "balanced"
{{humor_text}}      # "none" | "light" | "moderate"
{{encouragement_text}}  # "reserved" | "moderate" | "enthusiastic"

## Weitere Anweisungen
- LaTeX-Formatierung für mathematische Formeln ($...$ inline, $$...$$ display)
- Markdown-Formatierung für strukturierte Antworten
- Quiz-Erstellung: Automatisch bei Themenabschluss, Tool-Aufruf ist obligatorisch
- Detaillierte Anweisungen für Quiz-Erstellung (wann, wie, was nach Erstellung)
```

#### 2. QuickChatAgent System Prompt

**Langfuse Name**: `quickchat-agent/system-prompt`
- **Version**: 3 (production)
- **Type**: Chat prompt
- **Variables**: `{{formality_text}}`, `{{humor_text}}`, `{{encouragement_text}}`
- **Fallback**: Hardcoded fallback prompt available

**Key Structure**:

```
Du bist ein intelligenter Lernassistent, der Studenten hilft, Themen in ihren 
Vorlesungsmaterialien zu finden und zu verstehen.

## Deine Fähigkeiten

### Discovery-Modus (Standard)
- Suche mit `search_topic` Tool nach Themen in ALLEN Kursen
- Zeige alle Kurse mit `get_user_courses`
- Präsentiere relevante Seiten mit Kontext (Kurs, Material, Seitenzahl)

### Tutoring-Modus (nach Navigation zu einer Seite)
- **WICHTIG**: Bei JEDER Frage, rufe ZUERST `get_page_analysis` für die aktuelle Seite auf
- **FOKUS AUF AKTUELLE SEITE**: Interpretiere alle Fragen im Kontext der aktuellen Seite
- **SELTEN ANDERE VORLESUNGEN VORSCHLAGEN**: Nur wenn explizit gefragt oder offensichtlich nicht relevant
- **NAVIGATION MIT BESTÄTIGUNG**: Frage vor Navigation: "Soll ich zu [Material] auf Seite [X] navigieren?"

## Kommunikationsstil
{{formality_text}}
{{humor_text}}
{{encouragement_text}}
```

#### 3. QuizGeneratorAgent System Prompt

**Langfuse Name**: `quiz-generator/system-prompt-{language}`
- **German (DE)**: Version 2 (production)
- **Type**: Chat prompt
- **Variables**: None (static prompt)
- **Fallback**: Hardcoded fallback prompt available

**Key Structure**:

```
Du bist ein Quiz-Generator für Vorlesungsmaterialien. Deine Aufgabe ist es, 
Verständnisfragen zu erstellen, die das Verständnis der Studenten prüfen, 
nicht das Auswendiglernen.

WICHTIGE REGELN:
1. Erstelle 3-8 Fragen (max. 8)
2. Schwierigkeitsverteilung:
   - 1-2 leichte Fragen (Grundverständnis, Definitionen)
   - 1 mittlere Frage (Anwendung, Zusammenhänge)
   - Mindestens 1 schwere Frage (tiefes Verständnis, Analyse, Synthese)
3. Jede Frage muss genau 4 Antwortmöglichkeiten haben (A, B, C, D)
4. Fragen sollen VERSTÄNDNIS prüfen, nicht Auswendiglernen
5. Jede Frage braucht eine Erklärung der richtigen Antwort

FRAGEN-TYPEN (bevorzugt):
- Anwendungsfragen: "Wie würde man X in Situation Y anwenden?"
- Verständnisfragen: "Warum funktioniert X auf diese Weise?"
- Analysefragen: "Was wäre das Ergebnis, wenn man X ändert?"
- Synthesefragen: "Wie hängen X und Y zusammen?"

AUSGABE-FORMAT:
JSON-Format entsprechend QuizData Schema (topic, questions, metadata)
```

#### 4. FlashcardGeneratorAgent

**Note**: FlashcardGeneratorAgent does not use a traditional system prompt. Instead, it uses specialized prompts for different tasks that are loaded dynamically based on the material classification.

##### 4.1. Skip Decision Prompt

**Langfuse Name**: `flashcard-agent/skip-decision`
- **Version**: 2 (production)
- **Type**: Text prompt
- **Variables**: `{{summary}}`, `{{key_terms}}`
- **Output Format**: JSON with `{"skip": true/false, "reason": "..."}`

**Key Structure**:

```
Analysiere diese Vorlesungsseite und entscheide, ob sie übersprungen werden sollte.

Seitenzusammenfassung: {{summary}}
Wichtige Begriffe: {{key_terms}}

Überspringe die Seite, wenn sie:
- Eine Titelseite ist
- Ein Inhaltsverzeichnis ist
- Eine Einleitungsseite mit nur allgemeinen Informationen ist
- Eine Seite mit weiteren Informationen ist die nicht auswendig gelernt müssen 
  (z.B. Klausurtermin, Klausurinhalte, andere Veranstaltungen, Organisatorische 
  Informationen etc.)
- Keine fachlichen Inhalte enthält

Antworte mit JSON: {"skip": true/false, "reason": "Kurze Begründung"}
```

##### 4.2. Card Generation Prompt

**Langfuse Name**: `flashcard-agent/card-generation`
- **Version**: 10 (production)
- **Type**: Text prompt
- **Variables**: `{{summary}}`, `{{key_terms}}`, `{{exam_questions}}`, `{{diagram_description}}`, `{{conversation_context}}`, `{{snippet_image_url}}`, `{{course_id}}`, `{{material_id}}`, `{{page_number}}`
- **Output Format**: JSON with `{"cards": [{"front": "...", "back": "...", "tags": [...]}]}`
- **Domain Variants**: 
  - `card-generation-computer_science` (v2) - Extends base with CS-specific didactics
  - `card-generation-math` (v2) - Extends base with math-specific didactics and MathML examples
  - `card-generation-business_administration` (v1)
  - `card-generation-language_learning` (v1)
  - `card-generation-general` (v1)

**Key Structure** (simplified - actual prompt is ~1500 characters):

```
# ROLLE
Du bist ein erfahrener universitärer Tutor und Experte für die Erstellung 
effektiver Lernkarteikarten.

# INPUT DATEN
- Zusammenfassung: {{summary}}
- Wichtige Begriffe: {{key_terms}}
- Prüfungsfragen: {{exam_questions}}
- Diagrammbeschreibung: {{diagram_description}}
- Konversation/Kontext: {{conversation_context}}
- Visuelles Snippet: {{snippet_image_url}}

# ANWEISUNGEN
1. Lernziele identifizieren: Was ist die Kernaussage dieser Folie?
2. Kontext einbeziehen: Adressiere Verständnisprobleme aus der Konversation
3. Visuelles Snippet analysieren: Wenn vorhanden, analysiere das Bild und füge es 
   bei relevanten Karten ein (z.B. Diagramme, Formeln, Tabellen)
4. Karteikarten erstellen: Generiere 1-4 Karteikarten nach Atomizitätsprinzip
5. Zuordbar: Jede Karte soll ohne weiteren Kontext verständlich sein

# GRUNDREGELN
- Atomizität: Ein Konzept pro Karte
- Rückseite maximal 18 Wörter
- Präzise Fragen, keine Ja/Nein oder Aufzählungen
- Vollständiger Kontext in der Frage (z.B. "Python: Wer hat es entwickelt?")

# FORMATIERUNG DER RÜCKSEITE (WICHTIG!)
- Muss in HTML formatiert sein (nicht Markdown)
- Nutze <b>...</b> für Schlüsselbegriffe
- Nutze <ul><li>...</li></ul> für Aufzählungen
- Nutze <br> für Zeilenumbrüche
- BILD-EINFÜGUNG: Wenn Snippet relevant, füge am Ende ein:
  <br><br><img src="{{snippet_image_url}}" alt="Visual Snippet">
- Verwende MathML für mathematische Formeln (<math>, <mfrac>, <mroot>)
- KEIN Pipe-Symbol (|) im HTML verwenden!

# OUTPUT FORMAT
{
  "cards": [
    {
      "front": "Frage oder Begriff (Reintext)",
      "back": "HTML-String (z.B. <b>Definition:</b><br>Erklärung...",
      "tags": ["course:{{course_id}}", "material:{{material_id}}", 
               "page:{{page_number}}", "Thema"]
    }
  ]
}
```

**Domain-Specific Extensions**:

- **Computer Science** (`card-generation-computer_science`):
  - Fokus auf Abstraktionsebene (keine Code-Implementierung)
  - Bidirektionales Abfragen (Definition + Anwendung)
  - Prozess-Fokus bei Algorithmen (keine Syntax-Details)
  - `<code>...</code>` für technische Termini
  - MathML für Komplexitätsnotation (z.B. O(n))

- **Mathematics** (`card-generation-math`):
  - Fokus auf faktenbasiertes Wissen, Grundlagen, Prozesse
  - Definitionen, Kernformeln, Rechengesetze
  - Prozessorientierung (How-to Schritte)
  - MathML-Pflicht für alle mathematischen Ausdrücke
  - Detaillierte MathML-Beispiele für verschiedene Formeln

**Prompting Techniques:**

1. **ReAct (Reasoning and Acting)**: 
   - **Note**: ReAct is not explicitly mentioned in prompts, but emerges automatically through LangGraph architecture
   - The LangGraph workflow implements a ReAct-style loop: `agent → tools → agent → tools → ...`
   - The LLM (with tools bound via `llm.bind_tools()`) decides which tools to call based on the conversation context
   - The `should_continue` conditional routing automatically loops back to agent after tool execution
   - Tool usage is encouraged in prompts (e.g., "Verwende das get_page_analysis Tool, um Folieninhalte abzurufen, wenn nötig"), but the iterative loop is architectural
   - Example flow (automatic through graph execution):
     ```
     User: "What is a sequence diagram?"
     Agent (Reasoning): LLM decides to call get_page_analysis tool
     Agent (Action): Calls get_page_analysis tool (via ToolNode)
     Agent (Observation): Receives ToolMessage with {summary: "...", key_terms: ["sequence diagram", ...]}
     Agent (Reasoning): LLM processes tool result and generates response
     Agent (Response): "A sequence diagram is a UML diagram that shows..."
     ```

2. **Chain of Thought (CoT)**:
   - Structured reasoning is encouraged through prompt design (e.g., "Analyze... and decide" in flashcard skip-decision)
   - QuizGeneratorAgent structures questions by difficulty distribution (1-2 easy, 1 medium, at least 1 hard)
   - FlashcardGeneratorAgent explicitly reasons: "Should I skip this page? Why? What context do I need?" (via `PageSkipDecision` structured output)

3. **Structured Output**:
   - QuizGeneratorAgent uses `llm.with_structured_output(QuizData)` to guarantee valid Pydantic-validated output
   - FlashcardGeneratorAgent uses `PageSkipDecision` and `FlashcardGenerationResult` Pydantic models
   - Ensures consistent, parseable outputs without JSON parsing errors
   - Example:
   ```python
   structured_llm = llm.with_structured_output(QuizData)
   quiz_data = structured_llm.invoke(messages)
   # Guaranteed to be valid QuizData Pydantic model, no parsing errors
   ```

4. **Context Injection**:
   - State values (`current_page`, `material_id`, `user_id`) are automatically injected into system prompt
   - Tool arguments are automatically filled by `StateAwareToolNode` to prevent LLM hallucination
   - This is a form of "prompt engineering through code" rather than pure text prompts

**Prompt Evolution:**

1. **Initial Prompt** (v1): Simple "You are a helpful tutor" with basic tool descriptions
   - Problem: LLM hallucinated IDs (`course_material_id="test-id"`), didn't use tools consistently
   - Result: High tool-calling failure rate

2. **Added State Injection** (v2): Explicitly mentioned `current_page`, `material_id` in prompt
   - Problem: LLM still sometimes forgot to use tools or used wrong parameters
   - Result: Reduced but still significant tool-calling failures

3. **StateAwareToolNode** (v3): Automatic state injection at tool execution level
   - Solution: Prevents hallucination completely, LLM doesn't need to specify IDs
   - Result: Significantly reduced tool-calling failures

4. **Personality Variables** (v4): Added formality, humor, encouragement customization
   - Result: More personalized, engaging interactions

5. **Langfuse Integration** (v5-v12): Moved prompts to Langfuse for versioning and A/B testing
   - Benefit: Can update prompts without code changes, track prompt performance
   - Current: All prompts versioned in Langfuse with production labels
   - **Detailed Langfuse Prompt Evolution Summary**:

   **TutorAgent (`tutor-agent/system-prompt-de`)**:
     - **v1** (Jan 20, 2026): Initial prompt
       * Role: "persönlicher Professor" (personal professor)
       * Socratic method explicitly mentioned: "Stelle Fragen BEVOR du erklärst"
       * Basic tool descriptions (get_page_analysis, get_course_material_summary)
       * Personality variables (formality, humor, encouragement)
       * Communication style: "2-3 Sätze für Erklärungen, 1-2 für Fragen"
       * No quiz creation instructions
       * No formatting guidelines
     
     - **v5** (Jan 23, 2026): Major additions
       * **LaTeX formatting section added**: Comprehensive instructions for inline ($...$) and display ($$...$$) formulas
       * **Quiz creation section added**: Basic instructions for automatic quiz creation when subtopic completed
       * Quiz creation language: "WICHTIG" (important), not yet "KRITISCH" (critical)
       * Still "persönlicher Professor" (not yet changed to "Tutor")
       * Socratic method still present
     
     - **v10** (Jan 23, 2026): Major revision
       * **Role change**: "persönlicher Professor" → "persönlicher Tutor" (more approachable)
       * **Socratic method removed**: No longer explicitly asks questions before explaining
       * **Learning objectives emphasis added**: "Wichtig ist, dass du wirklich verstehst, was genau der Professor möchte, dass der Student mit dieser Folie lernt"
       * **Thematic linking added**: "Du kannst mehre inhalte der Vorlesung Thematisch verknüpfen"
       * **Markdown formatting section added**: Instructions for using headings, lists, bold, code blocks, blockquotes
       * **Quiz creation strengthened**: Changed from "WICHTIG" to "KRITISCH - BITTE GENAU BEFOLGEN"
       * **Quiz workflow detailed**: Step-by-step process (1) Recognize need → 2) Call tool → 3) Wait → 4) Confirm
       * **Quiz widget handling**: Explicit instruction not to output questions as text
       * **Communication style updated**: Removed specific sentence count, added "Maximal 4-7 Sätze"
     
     - **v12** (Jan 30, 2026 - current production): Final refinements
       * **User-initiated quiz section added**: "WENN DER USER NACH EINEM QUIZ FRAGT ODER DARAUF BESTEHT"
       * **Explicit tool call requirement**: "RUFE SOFORT DAS `create_quiz` TOOL AUF - KEINE Diskussionen, KEINE Rückfragen"
       * **Stop after quiz creation**: "KRITISCH - NACH QUIZ-ERSTELLUNG: ... sollst du NICHT weiter schreiben"
       * **Enhanced context awareness**: Better instructions for recognizing topic changes
       * **Communication style**: "Halt deine Antworten relevant. Maximal 4-7 Sätze"

   **FlashcardGeneratorAgent (`flashcard-agent/card-generation`)**:
     - **v1** (Jan 20, 2026): Initial simple prompt
       * Basic structure: Create 1-4 flashcards from page content
       * Simple JSON output format
       * No HTML formatting requirements
       * No visual snippet support
       * No MathML support
     
     - **v5** (Jan 26, 2026): Major overhaul
       * **Complete restructure**: New role definition, structured sections (ROLLE, INPUT DATEN, ANWEISUNGEN)
       * **HTML formatting requirement**: "Die Rückseite muss zwingend in **HTML** formatiert sein"
       * **MathML support added**: Instructions for using `<math>`, `<mfrac>`, `<mroot>` elements
       * **Visual snippet support added**: `{{snippet_image_url}}` variable with Handlebars conditional (`{{#if snippet_image_url}}`)
       * **Atomizität principle**: One concept per card, max 18 words on back
       * **Context requirement**: Cards must be understandable without additional context
       * **Pipe symbol restriction**: Explicit warning not to use `|` in HTML (used as separator in import for csv at that time)
     
     - **v10** (Jan 26, 2026 - current production): Snippet handling refinement
       * **Simplified snippet variable**: Changed from Handlebars conditional to direct `{{snippet_image_url}}` variable
       * **Vision-Input mention**: "Du siehst das Bild direkt in dieser Nachricht als Vision-Input"
       * **Enhanced snippet instructions**: More detailed guidance on when to include images (diagrams, formulas, tables, graphics)
       * **Explicit HTML code**: "Verwende EXAKT diesen HTML-Code: `<br><br><img src=\"{{snippet_image_url}}\" alt=\"Visual Snippet\">`"
       * **Empty snippet handling**: "Wenn kein Snippet vorhanden ist, wird {{snippet_image_url}} leer sein - dann füge KEIN img-Tag ein!"

   **QuizGeneratorAgent (`quiz-generator/system-prompt-de`)**:
     - **v1** (Jan 23, 2026): Initial prompt
       * Question count: "3-5 Fragen (max. 8)"
       * Difficulty distribution defined
       * Question types and avoidance rules
     
     - **v2** (Jan 28, 2026 - current production): Minor update
       * **Question count adjusted**: "3-8 Fragen" (removed "3-5", now allows 3-8 directly)

   **QuickChatAgent (`quickchat-agent/system-prompt`)**:
     - **v1** (Feb 1, 2026): Initial prompt
       * Basic Discovery and Tutoring modes
       * Simple mode switching description
       * No focus on current page context
     
     - **v3** (Feb 1, 2026 - current production): Context-aware revision
       * **Current page focus**: "FOKUS AUF AKTUELLE SEITE: Dein Hauptfokus liegt IMMER auf der aktuellen Seite"
       * **Context interpretation**: "Interpretiere alle Fragen im Kontext der aktuellen Seite"
       * **Rare cross-lecture suggestions**: "SELTEN ANDERE VORLESUNGEN VORSCHLAGEN" - only when explicitly asked
       * **Navigation confirmation**: "NAVIGATION MIT BESTÄTIGUNG" - must ask before navigating
       * **Explicit tool call**: "Bei JEDER Frage des Benutzers, rufe ZUERST `get_page_analysis` auf"
       * **Enhanced rules**: 8 detailed rules instead of 5 basic ones

   **Key Improvements Across All Agents**:
     - **Progressive refinement**: Each version addresses specific issues observed in production
     - **Explicit instructions**: Prompts became more prescriptive (e.g., "MUST" vs "should", "KRITISCH" vs "WICHTIG")
     - **Formatting standardization**: HTML for flashcards, LaTeX for math, Markdown for tutor responses
     - **Context awareness**: Better handling of current page, user state, and conversation context
     - **Visual content support**: Addition of `snippet_image_url` for flashcard generation with vision models
     - **Tool usage clarity**: Explicit instructions on when and how to call tools, with automatic injection emphasis

### 4.4. Context Engineering

**Context Structure:**

We structure context as:
```
[System Prompt (with state injection)]
+ [Conversation History (sliding window, last 10 messages)]
+ [Current User Query]
+ [Tool Results (if any, as ToolMessages)]
```

**Context Initialization Prompts (TutorAgent):**

The TutorAgent uses **3 specialized Langfuse prompts** to initialize context for different scenarios. These prompts are loaded as `HumanMessage` content (not system prompts) and provide contextual instructions for the agent's first response:

1. **`tutor-agent/first-visit`** (v2, production):
   - **Use Case**: First time student opens a specific lecture material
   - **Variables**: `{{page_number}}`, `{{total_pages}}`, `{{summary}}`
   - **Behavior**: Instructs agent to call `get_course_material_summary` tool first, then generate onboarding greeting
   - **Structure**: Hook → Priming (Big Picture) → Motivation → Call to Action
   - **Language**: German ("Du"-Form)

2. **`tutor-agent/welcome-back`** (v1, production):
   - **Use Case**: Student returns to study session after closing/reopening
   - **Variables**: `{{completed_pages}}`, `{{total_pages}}`, `{{topics_instructions}}`
   - **Behavior**: Generates personalized greeting referencing chat history topics
   - **Key Feature**: Extracts 2-5 most important topics from previous conversation (only actually discussed topics, not future announcements)
   - **Language**: German

3. **`tutor-agent/page-change-existing-thread`** (v1, production):
   - **Use Case**: Student navigates to new page when LangGraph state exists in MemorySaver (ongoing session)
   - **When this happens**: 
     * Page change within same backend process (state is still in MemorySaver)
     * Conversation history is already loaded in LangGraph state
   - **Variables**: `{{page_number}}`, `{{summary}}`
   - **Behavior**: Lighter hint, continues ongoing conversation naturally (less explicit since context is already established)
   - **Language**: German
   - **Technical Note**: Used when `is_new_thread = False` (snapshot exists with messages)


**Implementation**: These prompts are loaded via `get_tutor_prompt()` helper function in `/api/chat/initiate` endpoint and injected as `HumanMessage` content before the first agent response. They provide **contextual priming** rather than system-level instructions.

**Why HumanMessage instead of SystemMessage?**:
- **SystemMessage is persistent**: SystemMessages remain in conversation history and are sent with every LLM call. The `call_model()` method filters out old SystemMessages but preserves them in state, and `add_system_message()` only adds a SystemMessage if none exists (to prevent duplicates).
- **Init-Prompts are situational, not permanent**: `first-visit`, `welcome-back`, and `page-change` are one-time instructions for the agent's first response in a specific context. They should not be re-sent with every subsequent LLM call.
- **Token efficiency**: If these prompts were SystemMessages, they would consume tokens on every call, even though they're only relevant for the initial greeting.
- **Semantic correctness**: These prompts represent contextual user instructions ("greet the user", "explain the new page") rather than permanent system behavior. As `HumanMessage`, they are treated as user requests that the agent should respond to, which matches their purpose.
- **Existing SystemMessages**: The agent already has two SystemMessages: (1) the permanent system prompt (`tutor-agent/system-prompt-de`) defining role and behavior, and (2) a context SystemMessage with current page information. Adding init-prompts as SystemMessages would create unnecessary redundancy.

**Context Window Management:**

- **Sliding Window Approach**: TutorAgent keeps last 10 messages total (`MAX_HISTORY_MESSAGES = 10`)
  - **Note**: This is SystemMessage + up to 9 other messages (HumanMessage, AIMessage, ToolMessage)
  - **QuickChatAgent**: Uses 15 messages (`MAX_HISTORY_MESSAGES = 15`) for additional search context
  - **QuizGeneratorAgent & FlashcardGeneratorAgent**: No sliding window (batch processing, not conversational)

- **Tool Call Pairing**: AIMessage with `tool_calls` and corresponding ToolMessages are kept together (never split)
  - **Complex Logic**: If truncation would split a tool call pair, the incomplete AIMessage is removed
  - **Fallback**: If an AIMessage with tool_calls is removed, the system tries to include one additional older message (if it's not another incomplete tool call)

- **Priority**: Recent messages > Older messages. When limit reached, oldest messages removed first
- **SystemMessage Handling**: Old SystemMessages are discarded - `add_system_message()` sets the current system prompt (prevents duplicate system prompts)


**Context Retrieval:**

- **Agent-Specific Approaches**:
  - **TutorAgent, QuizGeneratorAgent, FlashcardGeneratorAgent**: Direct database access, NO RAG/vector search. Use structured JSONB queries:
    ```sql
    SELECT analysis_data FROM page_analyses 
    WHERE course_material_id = $1 AND page_number = $2
    ```
    - Rely on exact page number matching (faster, more reliable for page-specific queries)
    - No semantic search needed - these agents work with known page numbers
  
  - **QuickChatAgent (Discovery Mode)**: Uses RAG with Hybrid Search (Vector + Keyword)
    - **Vector Similarity Search**: Uses `search_pages_by_embedding()` RPC function with pgvector (HNSW index)
    - **Hybrid Search**: Combines vector similarity (60% weight) with keyword full-text search (40% weight) using Reciprocal Rank Fusion (RRF)
    - **Embedding Generation**: Query embeddings generated using Google `text-embedding-004` (768 dimensions)
    - **Fallback Strategy**: If embeddings unavailable, falls back to multi-keyword search with LLM-extracted keywords
    - **Best page to start revising**: `_pick_best_intro_page()` selects the best *introduction* page. When LLM is available, an LLM picks from top 15 candidates (Langfuse prompt `search-topic/intro-page-pick`). Otherwise a heuristic is used: chapter-heading fast path (prefer earliest), aggregate scoring (title, key_terms, continuity over next 6 pages from DB, semantic, material, synergy/chapter bonuses), first-of-block and earlier-block bonuses, and tie-breaking to earliest page in the top score band.
    - **Implementation**: `SearchTopicTool` uses `search_page_analyses_hybrid()` from `storage.py`
    - **Purpose**: Find relevant pages across all courses when user searches for topics (semantic similarity needed)

- **Structured Data**: Each page analysis contains pre-extracted `summary`, `key_terms`, `exam_questions`, `diagram_description` from Google Gemini 2.5 Flash (multimodal analysis)
- **Course Material Summary**: Retrieved via `get_course_material_summary` tool, cached in state (`course_material_summary` field)
  - **Token Optimization**: Summary only included in system prompt on first call or when material changes (saves ~200-500 tokens)
  - **Truncation**: Summary truncated to 500 characters with compact JSON formatting (saves ~200-1500 tokens/call)

**Context Compression/Summarization:**

- **Not Implemented**: We don't summarize older messages yet
- **Future Enhancement**: Could implement two-tier memory (detailed last 5 turns, summarized turns 6-15)

**Dynamic Context Selection:**

- **Mode-Based Context**: QuickChatAgent uses different context templates:
  - **Discovery Mode**: Uses RAG (hybrid vector + keyword search) via `search_topic` tool to find relevant pages across all courses. Includes `get_user_courses` tool results for course listing
  - **Tutoring Mode**: Switches to direct database access (no RAG) - includes `get_page_analysis` for current page, similar to TutorAgent
- **Tool-Specific Context**: When `create_quiz` is called, QuizGeneratorAgent receives only relevant page analyses (start_page to end_page), not entire conversation
- **State-Based Context Injection**: TutorAgent dynamically injects context into system prompt:
  - Always: `current_page`, `material_id`
  - Conditionally: `course_material_summary` (only on first call or material change)
  - Language-aware: German/English context strings based on `self.language`

## 5. Evaluation & Challenges

### Testing & Results

**Testing Approach:**

We tested agents through:
1. **Comprehensive Test Suite**: `test_all_agents.py` - A comprehensive automated test suite covering all agents, tools, and integrations. The test suite consists of 58 test cases organized into 7 main sections:
   - **Section 1: Import Tests** - Verifies all critical imports (BaseAgent, TutorAgent, FlashcardGeneratorAgent, QuizGeneratorAgent, QuickChatAgent, all 16+ tools, schemas, and services)
   - **Section 2: Tutor Agent Tests** - Tests TutorAgent initialization (default and custom personality configs), tool binding verification, state management, and message history sliding window
   - **Section 2.5: QuickChat Agent Tests** - Tests QuickChatAgent initialization, tool binding (6 tools: search_topic, get_user_courses, get_page_analysis, get_course_material_summary, create_quiz, get_page_image), state management, and tool execution
   - **Section 3: Flashcard Generator Agent Tests** - Tests FlashcardGeneratorAgent initialization, FlashcardState validation (17 required fields), and deduplication algorithm (both external and internal deduplication)
   - **Section 4: Quiz Generator Agent Tests** - Tests QuizGeneratorAgent initialization, language configuration, QuizData schema validation, and QuizQuestion options validation
   - **Section 5: Tool Tests** - Tests all 10 Anki tools (get_anki_deck_list, create_flashcard, create_flashcards_batch, search_anki_cards, get_anki_stats, etc.), TTS tool, Page Analysis Tool, Page Image Tool, Quiz Tool, Course Material Tool, and Knowledge Tool
   - **Section 6: Integration Tests** - Tests database connection (Supabase), Gemini LLM integration, Langfuse client, AnkiClient with cache, and full graph compilation for all agents
   - **Section 7: Error Handling Tests** - Tests graceful error handling for invalid material IDs, Anki not running scenarios, quiz validation errors, empty explanations, and flashcard deduplication edge cases

2. **Integration Tests**: Service-level integration tests with real database queries - `test_full_integration.py` tests the complete flow of Anki integration, flashcard caching, deduplication, and database operations. These tests directly call service functions (not HTTP endpoints) but use real Supabase database connections to verify end-to-end functionality including cache operations, Anki sync, deck renaming, and tag extraction. **Note**: The test script is safe to run as it uses unique test deck names (e.g., `TestCourse::TestLecture_Integration`, `FullIntegrationTest::Lecture1`) and performs cleanup after each test, but requires Anki to be running.

3. **Manual Testing**: Real study sessions with actual lecture PDFs (Software Engineering, Database Systems)

**Example 1: TutorAgent - Initializing New Lecture with Course Summary**

**Scenario:** User opens a Software Engineering lecture for the first time (starts on page 1).

**API Endpoint:** `/chat/initiate` (called when user opens a new lecture or navigates to a new page)

**Process:**
1. **API loads course material summary** (lines 928-931 in `endpoints.py`):
   ```python
   course_summary = get_course_material_summary(
       course_material_id=course_material_id,
       user_id=request.user_id
   )
   ```
   Returns: `{title: "Software Engineering", total_pages: 120, topics: ["UML", "Design Patterns", ...], ...}`

2. **API creates initial state** (lines 1461-1471):
   ```python
   initial_state = {
       "current_page": 1,  # First page when opening new lecture
       "material_id": "mat-123",
       "user_id": "user-456",
       "course_material_summary": course_summary,  # Injected here!
       "messages": [...]
   }
   ```

3. **TutorAgent detects material change** (line 686-687 in `tutor_agent.py`):
   ```python
   material_changed = (self._last_material_id is None or 
                      self._last_material_id != current_material_id)
   ```
   Since `_last_material_id` is `None` (first call), `material_changed = True`

4. **Agent injects summary into system prompt** (lines 691-706):
   - Summary is truncated to 500 chars to save tokens
   - Added to context as `VORLESUNGSÜBERSICHT` (Course Overview)
   - Only included on first call or when material changes (token optimization)

5. **Agent calls `get_page_analysis` tool** (automatic state injection via StateAwareToolNode):
   - `course_material_id="mat-123"` (from state)
   - `page_number=1` (from state - first page when opening new lecture)
   - `user_id="user-456"` (from state)

6. **Tool returns page-specific data**:
   ```json
   {
     "summary": "Introduction to Software Engineering: Overview of course structure, learning objectives, and key topics including UML diagrams, design patterns, and software architecture.",
     "key_terms": ["software engineering", "UML", "design patterns", "architecture"],
     "diagram_description": null
   }
   ```

**Agent Output:**
```
Hallo! 👋 Herzlich willkommen zur Vorlesung "Softwaretechnik: Design Patterns II". Schön, dass du da bist!

In dieser Vorlesung tauchen wir tief in die Welt der Entwurfsmuster ein. Wir werden uns speziell mit dem State-, Strategy- und Decorator-Pattern beschäftigen. Das Ziel ist, dass du am Ende nicht nur verstehst, wie diese Muster funktionieren, sondern auch, wann und wie du sie einsetzen kannst, um flexible und wartbare Software zu entwickeln. Stell dir vor, du lernst, wie man Software so baut, dass sie sich leicht an neue Anforderungen anpassen lässt, ohne dass alles auseinanderfällt – ziemlich cool, oder?

Du wirst lernen, wie man komplexe Probleme in der Softwareentwicklung elegant löst und deine Programme robuster und einfacher erweiterbar macht.

Bereit, loszulegen? Dann lass uns zur nächsten Folie springen oder frag mich, wenn du wissen möchtest, was uns in der kommenden Session alles erwartet! 😊
```

**Example 2: QuizGeneratorAgent Working Well**

**Input:** 
- Page analyses for pages 10-15 about "Object-Oriented Design Principles"
- Topic: "Encapsulation and Abstraction"

**Agent Process:**
1. QuizGeneratorAgent receives state: `{page_analyses: [...], topic: "Encapsulation", start_page: 10, end_page: 15}`
2. Builds context from page analyses: "Seite 10: Zusammenfassung: ... Wichtige Begriffe: ..."
3. Calls LLM with structured output: `llm.with_structured_output(QuizData)`
4. LLM generates 5 questions with difficulty distribution

**Output:** Generated 5 questions:
- **2 easy**: "What is encapsulation?" (definition), "Which keyword enforces encapsulation in Java?" (factual)
- **1 medium**: "How would you apply the Single Responsibility Principle to this class design?" (application)
- **2 hard**: "Analyze the trade-offs between inheritance and composition in this scenario" (analysis), "Design a class hierarchy that demonstrates both encapsulation and abstraction" (synthesis)


**Example 3: FlashcardGeneratorAgent Working Well**

**Input:** 
- 50-page PDF about "Software Engineering"
- Conversation history with 20 Q&A pairs
- Material classification: "computer science"

**Agent Process:**
1. Initializes: Loads all 50 page analyses and snippets
2. Classifies material: "computer_science" (cached in database)
3. For each page (0-49):
   - Skip decision: LLM decides to skip pages 0-2 (title, TOC, intro)
   - Gets context: Conversation messages for page, snippet URL if available
   - Generates cards: 1-2 flashcards per page using structured output
4. Deduplicates: Hash-based pre-filtering + similarity check (removed 3 duplicates)
5. Saves: Syncs 45 cards to Anki, caches in database

**Output:** Generated 45 flashcards (5 pages skipped), 3 duplicates removed, successfully synced to Anki


**Example 4: Agent Failing - Tool Hallucination (Fixed)**

**User Input:**
```
"Erkläre Seite 10"
```

**Agent Output (Before Fix):**
```
[Agent calls get_page_analysis with course_material_id="test-id", page_number=10]
[Tool returns error: Material not found]
[Agent responds: "I couldn't find the analysis for this page."]
```

**Why it failed:**
- LLM hallucinated `course_material_id="test-id"` instead of using actual `material_id="mat-123"` from state
- Tool couldn't find the material in database
- User received unhelpful error message

**Solution:**
- Implemented `StateAwareToolNode` that automatically injects `material_id` from state before tool execution
- LLM no longer needs to specify IDs, preventing hallucination
- Result: Significantly reduced tool-calling errors

**Example 5: Agent Struggling - Gemini API Tool Call Truncation**

**Scenario:** Agent calls multiple tools (e.g., `get_page_analysis` + `get_course_material_summary`) during a conversation with long message history.

**Problem:** 
- Gemini API returned incomplete tool calls (some tool calls were truncated in the response)
- When message history was truncated (sliding window), Tool-Call-Paare were broken apart:
  - AIMessage with `tool_calls` was kept, but corresponding `ToolMessage` responses were removed
  - This violated Gemini's strict message ordering requirements
- API errors: `Invalid message order: AIMessage with tool_calls must come immediately after HumanMessage or ToolMessage`
- Agent couldn't complete tool executions, leading to incomplete responses

**Why it struggled:**
- **Gemini API strict ordering**: Requires `HumanMessage → AIMessage(tool_calls) → ToolMessages → AIMessage` sequence
- **Message truncation**: When sliding window (10 messages) removed old messages, it sometimes cut in the middle of a tool-call pair
- **Incomplete tool calls**: Gemini sometimes returned partial tool calls that didn't have corresponding ToolMessages
- **No validation**: Initial implementation didn't check for incomplete tool-call pairs before sending to API

**Solution:**
- **`_fix_incomplete_tool_calls()` function** (lines 494-605 in `tutor_agent.py`):
  - Validates message ordering before every LLM call
  - Removes AIMessages with tool_calls that don't have corresponding ToolMessages
  - Removes orphaned ToolMessages (without preceding AIMessage)
  - Ensures AIMessage with tool_calls only comes after HumanMessage or ToolMessage
- **Safe truncation**: When truncating message history, ensures tool-call pairs stay together (lines 633-662)
- **Applied before every LLM call**: `messages_for_llm = self._fix_incomplete_tool_calls(messages_for_llm)` (line 836)
- **Same fix in API endpoints**: `fix_incomplete_tool_calls()` helper function in `endpoints.py` (lines 1050-1125)

**Result:** Agent now handles incomplete tool calls gracefully, preventing Gemini API errors and ensuring reliable tool execution.

### Challenges Faced

1. **Tool Argument Hallucination**
   - **Problem**: LLM sometimes generated incorrect IDs (`course_material_id="test-id"`) instead of using state values
   - **Impact**: Many tool calls failed due to invalid IDs
   - **Solution**: Implemented `StateAwareToolNode` that automatically injects state values before tool execution
   - **Result**: Dramatically reduced tool-calling errors

2. **Gemini API Message Order Requirements**
   - **Problem**: Gemini requires strict message order: HumanMessage → AIMessage (tool_calls) → ToolMessages. Incomplete tool call pairs (AIMessage with tool_calls but no ToolMessages) caused API errors.
   - **Impact**: Frequent API failures with "Invalid message order" errors
   - **Solution**: Implemented `_fix_incomplete_tool_calls()` that validates and removes incomplete pairs
   - **Result**: Significantly reduced API errors

3. **Flashcard Deduplication Performance**
   - **Problem**: Naive O(n²) similarity comparison for 1000+ cards was too slow (30+ seconds)
   - **Impact**: Poor user experience during flashcard generation
   - **Solution**: Implemented hash-based pre-filtering + optimized SequenceMatcher usage
   - **Result**: Reduced deduplication time from 30s to <2s for 1000 cards

4. **State Persistence Across Sessions**
   - **Problem**: Agent state (`current_page`, `material_id`) wasn't persisting between API calls
   - **Impact**: Agent lost context when user navigated to new page
   - **Solution**: Used LangGraph checkpointer with `thread_id = conversation_id`
   - **Result**: Seamless conversation continuity across page navigations

5. **Prompt Management and Versioning**
   - **Problem**: Hardcoded prompts made it difficult to iterate and test improvements
   - **Impact**: Required code deployment for every prompt change
   - **Solution**: Integrated Langfuse for prompt management with fallback to hardcoded versions
   - **Result**: Can now A/B test prompts without code deployments

6. **Observability and Usage Tracking**
   - **Problem**: Initially, consumption and usage patterns were unclear and unorganized. Prompt handling and model usage were difficult to track and analyze.
   - **Impact**: No visibility into API costs, token usage, or which prompts were being used. Difficult to optimize costs and debug issues.
   - **Solution**: Implemented comprehensive observability with Langfuse, including trace tracking, model cost monitoring, prompt versioning, and usage analytics
   - **Result**: Complete visibility into system behavior - can track all traces, monitor costs in real-time, analyze prompt performance, and identify optimization opportunities

### Limitations

1. **Context Window**: Sliding window of 10-15 messages may lose important context in very long conversations. No summarization implemented yet.

2. **No Proactive Calendar Management**: Planned but not implemented. Agents cannot yet schedule study sessions or adjust learning plans based on calendar.

3. **Limited Multi-Agent Coordination**: Agents work independently. No supervisor agent yet to coordinate between TutorAgent, QuizGeneratorAgent, and FlashcardGeneratorAgent.

4. **No Continual Learning**: Agents don't learn from user feedback or adapt prompts based on success/failure patterns. No feedback mechanism (thumbs up/down) implemented.

5. **Knowledge Mapping Not Agent-Integrated**: Anki study history and per-lecture mastery scores (0.0-1.0) are collected and stored, but agents don't yet use this data to adapt tutoring (e.g., focusing on weak topics or adjusting explanation depth based on mastery).

6. **Vision Input Limitations**: FlashcardGeneratorAgent can include snippet images, but not all pages have snippets. Some visual content may be missed in flashcard generation.

7. **Language Support**: Currently supports German and English. Adding more languages requires new Langfuse prompts and personality text translations.

8. **Error Recovery**: While checkpointer enables resumability, there's no automatic recovery. If flashcard generation fails at 80%, user must manually resume with same `thread_id`.

---

## 6. Theoretical Foundations: Agentic Characteristics

### Autonomy

**Assessment: Moderate to High Autonomy**

Our agents exhibit significant autonomy in decision-making:

- **Tool Selection**: TutorAgent autonomously decides which tools to use based on user queries. For example, if a user asks about a diagram, the agent decides to call `get_page_analysis` without explicit instruction. The LLM reasons: "User asks about content → I need page analysis → Call get_page_analysis tool."

- **Quiz Generation**: TutorAgent autonomously detects when a subtopic is completed (based on conversation context) and decides to create a quiz via `create_quiz` tool, without user request. Example: After explaining pages 10-15 about "Encapsulation", agent says "We've covered this topic. Let me create a quiz to test your understanding" and calls `create_quiz`.

- **Page Navigation**: QuickChatAgent autonomously navigates to matching pages when topics are found in discovery mode. When user searches "inheritance", agent finds it on page 23 and automatically opens that page.

- **Flashcard Skip Decisions**: FlashcardGeneratorAgent autonomously decides which pages to skip (intro/TOC pages) using LLM reasoning with structured output. No hardcoded rules.

**Limitations:**
- Agents cannot initiate new tasks without user input (no proactive study session scheduling yet)
- Agents cannot modify external systems beyond database (no calendar integration yet)

**Code Example:**
```python
# Agent autonomously decides to create quiz
# In TutorAgent.should_continue():
if last_message.tool_calls and last_message.tool_calls[0].name == "create_quiz":
    # Agent decided to create quiz, graph ends after quiz creation
    return "end"
```

### Social Ability

**Assessment: High Social Ability**

Our agents demonstrate strong social interaction capabilities:

- **Human-Computer Interaction**: All agents communicate naturally with students in German or English, adapting tone based on personality preferences (formality, humor, encouragement). Agents use conversational language, ask follow-up questions, and provide encouragement.

- **Agent-to-Agent Communication**: 
  - TutorAgent calls QuizGeneratorAgent via `create_quiz` tool (tool-based communication)
  - TutorAgent can trigger FlashcardGeneratorAgent (indirectly through services)
  - Agents share state through database (page_analyses, conversations)

- **Multi-Modal Communication**: Agents can reference visual content (diagrams, charts) from slides and include images in flashcard generation.

**Communication Protocols:**
- Tool-based communication: Agents communicate through standardized tool interfaces
- State sharing: Agents share context through Supabase database
- No direct agent-to-agent messaging yet (planned for supervisor agent)

**Example:**
```python
# TutorAgent communicates with QuizGeneratorAgent
quiz_result = create_quiz_tool.invoke({
    "start_page": 5,
    "end_page": 10,
    "course_material_id": "mat-123"
})
# QuizGeneratorAgent processes and returns quiz_data
# TutorAgent then presents quiz to user
```

### Reactiveness

**Assessment: Very High Reactiveness**

Our agents are highly reactive to environmental changes:

- **User Input**: Agents respond immediately to user messages with streaming responses for real-time feedback. Response time: ~500ms average.

- **Tool Results**: Agents react to tool outputs:
  - If `get_page_analysis` returns no data, agent explains this and offers alternatives: "This page hasn't been analyzed yet. Would you like me to analyze it?"
  - If `create_quiz` succeeds, agent informs user and presents quiz
  - If tool fails, agent handles error gracefully and continues

- **State Changes**: Agents react to state updates:
  - `current_page` changes → Agent loads new page analysis automatically
  - `material_id` changes → Agent loads new course summary
  - State changes trigger automatic context updates in system prompt

- **Error Handling**: Agents react to errors:
  - API failures → Fallback to cached data or graceful error messages
  - Invalid tool calls → StateAwareToolNode fixes before execution
  - Database errors → Agent explains issue to user

**Example:**
```python
# Agent reacts to page change
# In TutorAgent.call_model():
if state["current_page"] != previous_page:
    # Automatically loads new page analysis
    # System prompt updated with new current_page
    enhanced_prompt = f"{base_prompt}\n\nCONTEXT:\nCurrent page: {state['current_page']}"
```

### Proactiveness

**Assessment: Moderate Proactiveness**

Our agents show goal-directed behavior and take initiative:

- **Proactive Explanations**: TutorAgent proactively explains new slides when user navigates to a new page, without waiting for questions. Example: User navigates to page 15 → Agent automatically says "On this page, we're covering sequence diagrams. Let me explain..."

- **Proactive Quiz Creation**: TutorAgent proactively creates quizzes when detecting topic completion, rather than waiting for user request. Example: After covering pages 10-15, agent says "We've finished this topic. Here's a quiz to test your understanding!" and creates quiz.

- **Proactive Topic Suggestions**: QuickChatAgent proactively suggests related topics or pages when user searches for something. Example: User searches "inheritance" → Agent finds it and says "I found inheritance on page 23. The page is opening now."

- **Proactive Comprehension Checks**: TutorAgent proactively asks follow-up questions like "Do you understand why X happens?" to ensure understanding before proceeding.

**Limitations:**
- No proactive study session scheduling (calendar integration not implemented)
- No proactive notifications (e.g., "You haven't studied in 3 days")
- Agents don't initiate conversations without user input

**Example:**
```python
# Agent proactively creates quiz
# In TutorAgent, after detecting topic completion:
if topic_completed_detected:
    quiz = create_quiz_tool.invoke({
        "start_page": 5,
        "end_page": 10,
        "course_material_id": state["material_id"]
    })
    agent.respond("We've completed this topic. Here's your quiz!")
    # User didn't request quiz, agent took initiative
```

### Continual Learning

**Assessment: Limited Learning**

Our agents have limited continual learning capabilities:

- **Conversation Memory**: Agents use checkpointer to maintain conversation history within sessions, allowing them to reference earlier parts of the conversation. This is a form of short-term memory. Example: "As you asked earlier about encapsulation, here's how it relates to abstraction..."

- **Context Adaptation**: Agents adapt responses based on current conversation context. For example, if a user asks follow-up questions, the agent references previous explanations.

- **No Long-Term Learning**: Agents do not:
  - Update model weights
  - Learn from user feedback (thumbs up/down not implemented)
  - Adapt prompts based on success/failure patterns
  - Build knowledge base of successful interactions

**Potential Enhancements:**
- Store user feedback (correct/incorrect quiz answers) to adapt difficulty
- Track successful tool-call patterns and reuse them
- Learn user's learning style preferences over time
- Build vector store of successful Q&A pairs for retrieval
- **Use Anki mastery scores** (already collected) to adapt tutoring: focus on weak topics, adjust explanation depth, or suggest review sessions based on per-lecture mastery (0.0-1.0)

**Example:**
```python
# Current: Uses conversation history within session
history = agent.get_conversation_history(thread_id="conv-123")
# Can reference: "As you asked earlier..."

# Future: Could learn from feedback
if user_feedback == "helpful":
    store_successful_pattern(tool_call_pattern, user_query)
# Next time: Retrieve similar patterns and adapt
```

---

## 7. Ethical Considerations

### Bias & Fairness

**Potential Issues:**
- Language models may have biases from training data (gender, cultural, educational)
- Different students may receive different quality of explanations based on how well their questions match training data patterns
- Material classification (language_learning, math, business_administration, general) could reinforce stereotypes

**Mitigation Steps:**
- Tested agents with diverse query types and user personas
- Explicit instructions in system prompts to treat all users fairly
- Personality customization allows users to adapt communication style to their preferences
- Material classification is descriptive, not prescriptive (doesn't limit content)

**Future Improvements:**
- Collect user feedback on explanation quality
- Monitor for biased language in agent responses
- A/B test prompts with diverse user groups

### Privacy & Data Security

**Data Collected:**
- Conversation history (messages, tool calls)
- User preferences (personality, language)
- Learning progress (quiz results, flashcard completion)
- PDF content and analyses (stored in Supabase)
- Anki study history (if connected): Daily review stats, card states, and per-deck mastery scores synced via AnkiConnect and stored in `anki_study_history` table for knowledge mapping

**Data Handling:**
- All data stored in Supabase (PostgreSQL) with Row Level Security (RLS) policies
- User data is isolated by `user_id` - users can only access their own data
- Conversation history persisted in LangGraph checkpointer (PostgreSQL in production)
- No data shared with third parties except LLM providers (Google, OpenAI) for processing

**Privacy Concerns:**
- LLM providers (Google, OpenAI) may log API requests for training (we use their APIs)
- Conversation history could contain sensitive academic information
- PDF content is stored in Supabase Storage (encrypted at rest)

**Mitigation:**
- Users can delete course materials via UI, which cascades to delete associated Anki decks, flashcards, page analyses, and study history. Other data (conversation history, user preferences) cannot be manually deleted yet.
- RLS policies ensure data isolation
- Consider adding encryption for sensitive academic content
- Document data retention policies

### Transparency & Explainability

**Current State:**
- Agent reasoning is partially transparent: Tool calls are logged and can be viewed in Langfuse
- Users see tool results indirectly through agent explanations
- Internal tool selection logic (which tool to call) is not fully transparent to end users

**Transparency Features:**
- Langfuse tracing shows all LLM calls, tool invocations, and state transitions
- Frontend could show "Agent is analyzing page..." indicators
- Error messages explain what went wrong (e.g., "Page not analyzed yet")

**Limitations:**
- Users don't see the agent's internal reasoning (why it chose a specific tool)
- Tool argument injection (StateAwareToolNode) happens transparently but isn't explained to users
- Quiz/flashcard generation logic is opaque

**Future Improvements:**
- Add "thinking" indicators showing agent's reasoning steps
- Explain tool calls to users: "I'm looking up the analysis for this page..."
- Show confidence scores for agent responses

### Autonomy & Control

**Level of Autonomy:**
- Agents can autonomously call tools, create quizzes, generate flashcards
- Agents can navigate between pages (QuickChatAgent)
- Agents cannot modify external systems (no calendar integration yet)
- Agents cannot delete user data or modify user preferences autonomously

**Safeguards:**
- All tool calls are logged and traceable (Langfuse)
- Users can interrupt agent execution (stop button in UI)
- Quiz/flashcard generation requires explicit user request (not fully autonomous)
- No autonomous actions that modify external systems

**User Control:**
- Users can stop agent execution at any time
- Users can delete conversations
- Users can modify personality preferences
- Users can choose which materials to analyze

**Future Considerations:**
- If calendar integration is added, require user confirmation for scheduling
- Add "undo" functionality for agent actions
- Allow users to review and edit generated quizzes/flashcards before saving

### Misuse & Safety

**Potential Misuse:**
- Students could use agents to generate answers for exams (academic dishonesty)
- Agents could generate misleading or incorrect information if PDF analysis is wrong
- Flashcard generation could create incorrect study materials

**Safety Measures:**
- Agents are designed for learning support, not exam cheating
- System prompts emphasize comprehension over memorization
- Quiz questions test understanding, not just facts
- Users should verify generated content (quizzes, flashcards) before using

**Content Safety:**
- No content filtering implemented (agents will explain any academic content)
- No restrictions on what materials can be uploaded
- Consider adding content warnings for sensitive topics

**Rate Limiting:**
- Not yet implemented, but should be added to prevent API abuse
- Consider limiting number of quiz/flashcard generations per user per day

### Accountability

**Error Handling:**
- Agents clearly indicate uncertainty: "I'm not sure about this, let me check the page analysis"
- Errors are logged with timestamps and user context (Langfuse)
- Tool failures are explained to users: "The page analysis couldn't be found"

**Responsibility:**
- System is a learning aid, not a replacement for studying
- Users are responsible for verifying information
- We (developers) are responsible for system reliability and data security

**Error Recovery:**
- Agents gracefully handle errors and continue operation
- Checkpointing allows recovery from failures (FlashcardGeneratorAgent can resume)
- Fallback prompts if Langfuse is unavailable

**Future Improvements:**
- Add user feedback mechanism (report incorrect information)
- Implement error tracking and alerting
- Create user support channel for issues

---

## 8. Conclusion & Future Work

### Conclusion

We successfully built **Lernkompanien**, a multi-agent adaptive learning system that addresses real challenges students face when studying lecture materials. Our system demonstrates strong agentic characteristics:

**Achievements:**
- ✅ **Four Specialized Agents**: TutorAgent, QuickChatAgent, QuizGeneratorAgent, and FlashcardGeneratorAgent, each with distinct responsibilities and LangGraph state machines
- ✅ **Multimodal Content Analysis**: Successfully extracts structured information from PDF slides using Google Gemini 2.5 Flash (multimodal)
- ✅ **Context-Aware Tutoring**: Agents maintain conversation context across sessions using LangGraph checkpointer
- ✅ **Proactive Behavior**: Agents create quizzes and flashcards autonomously when appropriate
- ✅ **Personalization**: Communication style adapts to user preferences (formality, humor, encouragement)
- ✅ **Robust Architecture**: StateAwareToolNode eliminates tool-calling errors, Langfuse enables prompt versioning

**Key Takeaways:**
1. **State Management is Critical**: Automatic state injection (StateAwareToolNode) dramatically reduced tool-calling errors
2. **Prompt Engineering Requires Iteration**: Moving prompts to Langfuse enabled rapid iteration and A/B testing
3. **Structured Output is Essential**: Using Pydantic models with `with_structured_output()` ensures reliable JSON generation
4. **Context Window Management**: Sliding window approach balances context retention with token limits
5. **Agentic Systems Need Observability**: Langfuse tracing was crucial for debugging and understanding agent behavior

**Objectives Met:**
- ✅ Content understanding (multimodal analysis)
- ✅ Context-aware tutoring
- ✅ Proactive quiz generation
- ✅ Flashcard generation with deduplication
- ✅ Topic discovery across courses
- ✅ Personalization

**Objectives Partially Met:**
- ⚠️ Calendar management (planned but not implemented)

### Future Work

If we had another month, we would prioritize:

1. **Supervisor Agent**
   - Background agent that monitors learning progress
   - Compares planned vs. actual progress (Should-Is comparison)
   - Automatically adjusts study plans
   - Coordinates between other agents

2. **Calendar Integration**
   - Google Calendar sync for study session scheduling
   - Automatic blocking of learning units into free time slots
   - Proactive notifications: "Hey, Statistics is scheduled today. Should we start?"

3. **Continual Learning**
   - User feedback mechanism (thumbs up/down on explanations)
   - Track successful tool-call patterns
   - Adapt prompts based on user success rates
   - Build knowledge base of effective teaching strategies

4. **Enhanced Context Management**
   - Summarize older conversation turns to maintain longer context
   - Two-tier memory: detailed (last 2 turns) + summarized (turns 3-10)
   - Semantic search across conversation history

5. **Multi-Agent Coordination**
   - Supervisor agent coordinates TutorAgent, QuizGeneratorAgent, FlashcardGeneratorAgent
   - Agents can request help from each other
   - Shared memory/state between agents

6. **Advanced Personalization**
   - Learn user's preferred learning style over time
   - Adapt explanation depth based on user's comprehension level
   - Personalized quiz difficulty adjustment

7. **Performance Optimizations**
   - Batch processing for multiple page analyses
   - Caching of frequently accessed page analyses
   - Parallel tool execution where possible

8. **User Experience Improvements**
   - Real-time collaboration (multiple students studying together)
   - Voice input/output for hands-free studying
   - Mobile app for on-the-go learning

---

## 9. References

- Wooldridge, M., & Jennings, N. R. (1995). Intelligent agents: Theory and practice. The Knowledge Engineering Review, 10(2), 115–152. https://doi.org/10.1017/S0269888900008122

- LangChain Documentation. (2024). "Agents." https://python.langchain.com/docs/modules/agents/

- LangGraph Documentation. (2024). "Getting Started." https://langchain-ai.github.io/langgraph/

- Google Gemini API Documentation. (2024). "Gemini 2.5 Flash Model." https://ai.google.dev/models/gemini

- Google Gemini API Documentation. (2024). "Gemini Multimodal Capabilities." https://ai.google.dev/models/gemini

- Langfuse Documentation. (2024). "Prompt Management." https://langfuse.com/docs/prompts

- Supabase Documentation. (2024). "Row Level Security." https://supabase.com/docs/guides/auth/row-level-security

- AnkiConnect API. (2024). "AnkiConnect Documentation." https://github.com/FooSoft/anki-connect

---

## 10. Individual Contribution Log

### Milan Elias Mayer (mmayer11@smail.uni-koeln.de)

**Major Contributions:**

- **QuickChatAgent Development**: Developed the QuickChatAgent for topic discovery across multiple courses, including:
  - Dual-mode operation (discovery and tutoring modes) with automatic mode switching
  - Hybrid search implementation (vector + keyword with RRF fusion)
  - Best page to start revising: LLM-based intro pick (Langfuse prompt) when available, plus heuristic `_pick_best_intro_page()` (chapter headings, aggregate scoring, continuity over next 6 pages, first-of-block/earlier-block bonuses)
  - StateAwareToolNode integration to prevent LLM hallucination of IDs

- **FlashcardGeneratorAgent**: Refactored and expanded the FlashcardGeneratorAgent:
  - LangGraph state machine with real-time progress tracking via SSE
  - PostgreSQL persistency for resumable generation across backend restarts
  - Classification-based prompt routing for material-specific flashcard generation
  - Hash-based deduplication (O(n) instead of O(n²), reduced time from 30s to <2s for 1000 cards)

- **Tool Development**: Created multiple LangChain tools:
  - `SearchTopicTool` - Hybrid RAG search with LLM/heuristic best intro page selection
  - `KnowledgeTool` - Per-course mastery scores from Anki study data
  - `TTSTool` - Text-to-speech with multi-language support
  - 10+ Anki tools (deck management, flashcard sync, study history)

- **Backend API**: Developed FastAPI endpoints for:
  - QuickChat messaging and streaming (`/api/quickchat/message`)
  - Anki integration (`/api/anki/study-history`, `/api/anki/sync`, `/api/anki/knowledge`)
  - Flashcard generation with progress tracking and background tasks
  - Course material deletion with cascade cleanup

- **Anki Integration**: Implemented complete Anki ecosystem with Docker support (`ankimcp/headless-anki` ARM64), native app fallback, AnkiWeb sync with programmatic login, sync conflict management, and knowledge tracking with per-deck mastery scores.

- **Search & RAG System**: Optimized topic search with hybrid vector + keyword search (RRF fusion). Best page to start revising: LLM-based intro pick from top candidates (Langfuse prompt) when available, else heuristic `_pick_best_intro_page()` (chapter-heading fast path, aggregate scoring with continuity over next 6 pages, first-of-block/earlier-block bonuses, tie-break to earliest page).

- **Frontend Development**: Quick Chat interface with inline PDF viewer, dashboard with Anki study history, settings modal, real-time progress tracking for PDF processing and flashcard generation.

- **Performance Optimizations**: Reduced agent token usage per LLM call, added backend caching and frontend memoization, hash-based deduplication (O(n) instead of O(n²)).

- **Prompt Engineering**: Developed system prompts for FlashcardGeneratorAgent (with classification-based routing for different material types), QuickChatAgent (discovery and tutoring modes), and material classification prompts.

- **Testing & Documentation**: Created comprehensive test suite (`test_all_agents.py`) with 16+ test cases. Wrote `AGENT_ANALYSE_UND_DOKUMENTATION.md`.

**Git Commits (Sample):**
- `feat(quickchat): add Quick Chat with inline PDF viewer and navigation confirmation`
- `feat: refactor FlashcardGeneratorAgent to LangGraph and implement progress tracking`
- `feat(search): optimize search algorithm with hybrid vector + keyword search`
- `feat(anki): add knowledge tracking with per-deck mastery scores`
- `feat(classification): implement classification-based prompt routing`
- `perf: reduce agent token usage by 40-60% per LLM call`

### Detailed Contribution Analysis: Louis Braukmann
**Role:** Full Stack Lead & AI Engineer
**Analysis Period:** Jan 10, 2026 - Jan 27, 2026

#### 1. Executive Summary
Louis Braukmann acted as the primary architect and lead developer for the Lernkompanien project. His contributions span the entire stack, establishing the "Vision-First" AI architecture, the Next.js frontend foundation, and the FastAPI backend infrastructure. He was responsible for the critical implementation of the LangGraph-based agentic workflows (Tutor, Quiz, Flashcard), the robust multimodal ingestion pipeline (PDF to Image to Structured Data), and the final production hardening (Langfuse observability, custom hooks for streaming, and Anki integration).

#### 2. Chronological Contribution Timeline

##### Phase 1: Architectural Foundation & Vision-First Ingestion (Jan 10)
Louis initiated the project by defining the core architecture and development standards, moving away from traditional RAG to a multimodal approach.

*   **Repository & Standards Initialization**:
    *   Created `AGENT_DEVELOPMENT_RULES.md` to define strict typing and LangGraph patterns.
    *   Set up the monorepo structure: `frontend` (Next.js 14 App Router) and `backend` (FastAPI).
    *   Implemented `PROJECT_PLAN.md` and initial Cursor rules.
*   **Database Design**: Designed and applied the initial Supabase SQL schema (`20260110...initial_schema.sql`), establishing the core relational structure for courses, materials, and users.
*   **The "Vision-First" Pivot**:
    *   Wrote `poc_vision_gemini.py` to validate using Multimodal LLMs (Gemini Flash) for reading lecture slides as images instead of OCR text extraction.
    *   Implemented the asynchronous PDF processing pipeline using FastAPI `BackgroundTasks` to handle large lectures without blocking requests.

##### Phase 2: Core MVP & Feature Implementation (Jan 12 - Jan 17)
Focused on building the user interface and connecting the basic agentic loops.

*   **Frontend Infrastructure**:
    *   Implemented the entire dashboard using **shadcn/ui** components.
    *   Built the Authentication flow using Supabase SSR (`frontend/lib/auth.ts`, Middleware).
    *   Created the "Split-Screen" study interface (`StudyReader`), allowing side-by-side PDF viewing and AI chat.
*   **Course Management**:
    *   Developed full CRUD API endpoints for Courses and Learning Units.
    *   Implemented file uploads with `pdf2image` integration for converting PDF pages to analyzing images.
*   **Tutor Agent Prototype**:
    *   Created the initial `TutorAgent` using LangGraph.
    *   Implemented state injection mechanisms to allow agents to "see" the user's current page in the PDF.

##### Phase 3: Agent Maturity, Refactoring & Production Polish (Jan 20 - Jan 27)
The most active phase, focused on reliability, observability, and advanced AI features.

*   **Flashcard Agent: From Inception to Anki Integration**:
    *   **Initial Creation (Jan 20)**: Built the `FlashcardAgent` from scratch, defining the LangGraph nodes and structured output schemas to generate flashcards from lecture content.
    *   **Evolution**: Evolved the system from simple JSON/CSV export to generating full **Anki decks (`.apkg`)**.
    *   **Tech**: Integrated `genanki` to bundle base64 images directly into Anki cards (critical for math/diagram-heavy lectures).
    *   **UI**: Added snippet selection tools allowing users to crop multiple distinct areas of a slide for flashcards.
*   **Quiz Agent Rewrite & UI**:
    *   **Agent**: Refactored `QuizGeneratorAgent` from scratch to fix state consistency bugs and implemented `quiz_creation_lock.py` to prevent race conditions.
    *   **UI**: Designed and implemented the interactive `QuizComponent` widget (`frontend/components/study/quiz-component.tsx`), handling user selection, feedback display, and result tracking.
*   **Observability (DevOps)**:
    *   **Langfuse Integration**: Completely integrated Langfuse for tracing agent steps, prompts, and costs (`backend/app/services/observability.py`).
    *   Migrated all hardcoded prompts to Langfuse Prompt Management, enabling version control for prompts.
*   **Frontend Performance & UX**:
    *   **Math Rendering**: Migrated chat rendering from MathJax to **KaTeX** for faster, OpenAI-compatible LaTeX rendering.
    *   **Custom Hooks**: Refactored the monolithic `StudyReader` into modular hooks:
        *   `useChatSession`: Handles SSE streaming, history, and optimistic updates.
        *   `useTypewriter`: Handles the "typing effect" for AI messages.
    *   **Streaming**: Fixed critical SSE (Server-Sent Events) issues to ensure smooth token streaming without JSON parsing errors.

#### 3. Technical Deep Dive & Key Innovations

##### A. The "StateAwareToolNode" Pattern
To solve the issue of LLMs losing context of the user's UI state, Louis implemented a custom `StateAwareToolNode` in the backend.
*   **Problem**: Standard LangChain tools didn't know which PDF page the user was looking at.
*   **Solution**: He intercepted the tool execution loop to inject `current_page_context` and `slide_analysis` directly into the tool's runtime args before the LLM logic executed.
*   **Impact**: Dramatically reduced hallucination when users asked "Explain this slide".

##### B. Asynchronous Multimodal Ingestion
Instead of simple text extraction, Louis built a pipeline that "sees" the lecture:
1.  **Upload**: PDF is uploaded to Supabase Storage.
2.  **Processing**: `pdf_processor.py` runs in a background thread.
3.  **Conversion**: Uses `pdf2image` to convert pages to high-res JPEGs.
4.  **Analysis**: Sends images to Gemini 2.5 Flash for structured JSON extraction (Summary, Key Terms, Exam Questions).
5.  **Storage**: Saves structured analysis in `page_analyses` (JSONB) for retrieval by agents.

##### C. Robust Frontend Streaming Architecture
Louis refactored the chat interface (`useChatSession.ts`) to handle complex streaming requirements:
*   **Hybrid State**: Manages local optimistic UI state while syncing with Supabase database.
*   **Stream Parsing**: Handles raw text streams mixed with tool call markers using a robust parsing logic in `frontend/lib/api/study.ts`.
*   **Debounced Navigation**: Implemented debouncing for page flips to prevent flooding the Tutor Agent with context updates.

##### D. Flashcard & Snippet System
*   **Multi-Snippet Support**: Added ability to select *multiple* distinct regions on a single PDF page to generate separate flashcards.
*   **Anki Engineering**: Wrote `langfuse_to_anki_csv.py` and service layers to package media files and HTML content into importable Anki packages, moving beyond simple text cards.

#### 4. Summary of Git Statistics
*   **Commits Analyzed**: ~50+ significant commits.
*   **Key Files Created/Owned**:
    *   `backend/app/agents/tutor/tutor_agent.py`
    *   `backend/app/services/pdf_processor.py`
    *   `frontend/hooks/use-chat-session.ts`
    *   `frontend/components/study/study-reader.tsx`
*   **Technologies Introduced**: LangGraph, Supabase SSR, Langfuse, Genanki, KaTeX, Framer Motion (for typewriter effects).

**Collaboration:**
- Both team members worked closely on integrating agents, debugging tool-calling issues, and refining the overall architecture.
- Regular code reviews and pair programming sessions for complex features like Anki integration and state management.
- Shared responsibility for documentation and testing.

---

**Report Generated**: 2025-01-26  
**Project Repository**: https://github.com/lquick33/AgenticAI_Group03
**Last Updated**: 2025-01-26
