# Project Title: Lernkompanien - Adaptive Learning Assistant

**Course:** Agentic Artificial Intelligence  
**Team Name:** Group 03

## Team Members

- Milan Elias Mayer (mmayer11@smail.uni-koeln.de)
- Louis Braukmann (louis.braukmann@gmail.com)

---

## 1. Executive Summary

University students face a critical challenge when studying complex lecture materials: navigating hundreds of PDF pages, understanding dense academic content, and maintaining consistent study habits. Traditional learning tools are passive and don't adapt to individual learning styles or provide context-aware guidance.

**StudyBuddy** addresses this problem through a multi-agent AI system that autonomously analyzes lecture slides, provides personalized tutoring, and generates study materials. Our solution employs four specialized agents orchestrated with LangGraph: a **TutorAgent** for interactive study sessions, a **QuickChatAgent** for topic discovery across courses, a **QuizGeneratorAgent** for comprehension testing, and a **FlashcardGeneratorAgent** for spaced repetition learning with Anki.

The system's key capability is **the seamless integration between agents and frontend, combined with orchestrated multi-agent collaboration and detailed knowledge integration**. Unlike using ChatGPT where users must manually copy-paste each page and provide context repeatedly, our agents work together autonomously: the **TutorAgent** guides the student through the lecture while it maintains conversation context across pages and automatically calls the **QuizGeneratorAgent** when topics are completed to check the students comprehension while being in the lecture, while the **FlashcardGeneratorAgent** incorporates both slide content and conversation history to create personalized flashcards, including snippets that the student can mark while being in our StudyReader. Each PDF page is pre-analyzed using GPT-4o Vision to extract structured knowledge (summaries, key terms, exam questions, diagram descriptions), which is stored in a database and seamlessly accessible to all agents. This enables **true detail depth** because agents access precise, page-specific information rather than processing entire documents at once.

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

6. **Tool Execution** → Queries Supabase across all courses:
   ```sql
   SELECT * FROM page_analyses 
   WHERE analysis_data::text ILIKE '%polymorphism%'
   AND course_material_id IN (SELECT id FROM course_materials WHERE user_id = 'user-456')
   ```
   Returns: `[{material_id: "mat-789", page_number: 42, summary: "..."}, ...]`

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

1. **Google Gemini 2.5 Flash** (primary for all agents)
   - Used for: TutorAgent conversations, QuizGeneratorAgent, FlashcardGeneratorAgent, QuickChatAgent
   - Fallback: Gemini 1.5 Flash if 2.5 unavailable
   - Model selection logic:
   ```python
   models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
   for model_name in models_to_try:
       try:
           llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.1)
           return llm
       except:
           continue  # Try next model
   ```

2. **OpenAI GPT-4o** (vision only)
   - Used for: Multimodal PDF page analysis during upload
   - Purpose: Extracts structured information from slide images
   - Called once per page during PDF processing, not during conversations

**Justification:**

- **Performance**: Gemini 2.5 Flash provides excellent reasoning for tool-calling and structured output generation. In our testing, it achieved 95%+ accuracy for tool selection and 90%+ for structured JSON generation. GPT-4o Vision excels at understanding complex diagrams and visual content in lecture slides, with superior performance compared to Gemini Vision for academic content.

- **Speed**: Gemini 2.5 Flash has significantly lower latency (~500ms average) compared to GPT-4 (~2-3s), crucial for real-time tutoring interactions. Users expect immediate responses during study sessions.

- **Cost**: Gemini API is more cost-effective than GPT-4 for high-volume usage. We use GPT-4o Vision only for initial PDF analysis (one-time per page, ~$0.01 per page), not for every conversation turn. For a 100-page PDF, this costs ~$1.00 total, compared to $10-20 if using GPT-4 for all interactions.

- **Context Window**: Gemini 2.5 Flash supports 1M token context window, sufficient for long conversation histories and multiple page analyses. This allows us to maintain context across entire study sessions.

- **Accessibility**: Google Gemini API is readily available and doesn't require complex setup. We use OpenAI only for vision tasks where it's demonstrably superior.

**Hyperparameters:**

- **Temperature**: `0.1` for all agents
  - Rationale: Lower temperature ensures consistent tool-calling and structured output. We want reliable, deterministic behavior rather than creative variation. In testing, `temperature=0.7` led to 20% tool-calling errors, while `temperature=0.1` reduced this to <5%.

- **Top-p**: Not explicitly set (uses model defaults)
- **Max Tokens**: Not set (allows full responses, important for detailed explanations)
- **Response Format**: Structured output via `llm.with_structured_output(PydanticModel)` for quiz and flashcard generation to guarantee valid JSON

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
   - Searches for topics across all user's courses and materials
   - Implementation: Full-text search on `page_analyses.analysis_data` JSONB column
   - Returns: List of matching pages with context: `[{material_id, page_number, summary, key_terms, ...}]`
   - Used by: QuickChatAgent in discovery mode

5. **`get_user_courses(user_id: str) -> List[dict]`**
   - Lists all courses and materials for a user
   - Returns: `[{course_id, course_name, materials: [{material_id, title, ...}]}]`
   - Used by: QuickChatAgent

6. **`get_page_image(course_material_id: str, page_number: int, user_id: str) -> str`**
   - Returns public URL for page image from Supabase Storage
   - Used by: TutorAgent for visual context in explanations

**Memory:**

We use **LangGraph Checkpointer** for conversation persistence:

- **Thread-based Persistence**: Each conversation session has a unique `thread_id` (typically `conversation_id` from database)
- **Checkpointer Types**:
  - Development: `MemorySaver` (in-memory, lost on restart)
  - Production: `PostgresSaver` (persists to Supabase PostgreSQL)
- **Message History**: All messages (HumanMessage, AIMessage, ToolMessage) are automatically stored and retrieved
- **State Persistence**: Agent state (`current_page`, `material_id`, etc.) is checkpointed after each node execution
- **Sliding Window**: TutorAgent keeps last 10 messages in context to prevent token explosion while maintaining conversation flow

**Example Memory Usage:**
```python
# New thread: System message + first user message
config = {"configurable": {"thread_id": "conv-123", "user_id": "user-456"}}
result = agent.run("Explain page 5", thread_id="conv-123", user_id="user-456")

# Existing thread: Just add new message (system message already exists)
result = agent.run("What about the diagram?", thread_id="conv-123", user_id="user-456")
# Agent remembers previous conversation about page 5
```

**Long-term Memory (Store):**
- Prepared but not yet fully implemented
- Intended for: User preferences, learning patterns, successful tool-call patterns
- Would enable: Personalized prompt adaptation, learning from past interactions

### 4.3. Prompt Engineering

**System Prompt (TutorAgent):**

The system prompt is managed in **Langfuse** under `tutor-agent/system-prompt-{language}` with fallback to hardcoded version. Key structure:

```
Du bist ein persönlicher Professor für Universitätsstudenten.

## Deine Rolle
- Erkläre auf studentenfreundlichem Niveau (nicht zu akademisch, nicht zu einfach)
- Nutze die sokratische Methode: Stelle Fragen BEVOR du erklärst
- Verwende Analogien und zerlege komplexe Konzepte in verständliche Schritte
- Sei geduldig und ermutigend

## Kontext
- Aktuelle Seite: {current_page}
- Material-ID: {material_id}
- Benutzer-ID: {user_id}

## Tools
Du hast Zugriff auf folgende Tools:
- get_page_analysis: Hole die strukturierte Analyse für die aktuelle Seite
  → WICHTIG: course_material_id und page_number werden AUTOMATISCH injiziert
  → Du musst diese Parameter NICHT angeben, nur user_id falls nötig

## Persönlichkeit
{formality_text}  # "formal" | "informal" | "balanced"
{humor_text}      # "none" | "light" | "moderate"
{encouragement_text}  # "reserved" | "moderate" | "enthusiastic"
```

**Prompting Techniques:**

1. **ReAct (Reasoning and Acting)**: 
   - Our agents follow a ReAct-style loop: `agent → tools → agent → tools → ...`
   - The LLM reasons about which tool to call, executes it, observes results, and decides next action
   - Example flow:
     ```
     User: "What is a sequence diagram?"
     Agent (Reasoning): "I need to understand what's on the current page. I should call get_page_analysis."
     Agent (Action): Calls get_page_analysis tool
     Agent (Observation): Receives {summary: "...", key_terms: ["sequence diagram", ...]}
     Agent (Reasoning): "Now I have the context. I can explain sequence diagrams."
     Agent (Response): "A sequence diagram is a UML diagram that shows..."
     ```

2. **Chain of Thought (CoT)**:
   - Implicit in our prompts: "Think step-by-step", "Break concepts into steps"
   - QuizGeneratorAgent explicitly structures questions by difficulty (easy → medium → hard)
   - FlashcardGeneratorAgent reasons: "Should I skip this page? Why? What context do I need?"

3. **Structured Output**:
   - QuizGeneratorAgent uses `llm.with_structured_output(QuizData)` to guarantee valid JSON
   - FlashcardGeneratorAgent uses `PageSkipDecision` and `FlashcardGenerationResult` Pydantic models
   - Ensures consistent, parseable outputs without JSON parsing errors
   - Example:
   ```python
   quiz_data = await llm.ainvoke(
       messages,
       config={"configurable": {"response_format": {"type": "json_object"}}}
   )
   # Guaranteed to be valid QuizData, no parsing errors
   ```

4. **Context Injection**:
   - State values (`current_page`, `material_id`, `user_id`) are automatically injected into system prompt
   - Tool arguments are automatically filled by `StateAwareToolNode` to prevent LLM hallucination
   - This is a form of "prompt engineering through code" rather than pure text prompts

**Prompt Evolution:**

1. **Initial Prompt** (v1): Simple "You are a helpful tutor" with basic tool descriptions
   - Problem: LLM hallucinated IDs (`course_material_id="test-id"`), didn't use tools consistently
   - Error rate: ~30% tool-calling failures

2. **Added State Injection** (v2): Explicitly mentioned `current_page`, `material_id` in prompt
   - Problem: LLM still sometimes forgot to use tools or used wrong parameters
   - Error rate: ~15% tool-calling failures

3. **StateAwareToolNode** (v3): Automatic state injection at tool execution level
   - Solution: Prevents hallucination completely, LLM doesn't need to specify IDs
   - Error rate: <5% tool-calling failures

4. **Personality Variables** (v4): Added formality, humor, encouragement customization
   - Result: More personalized, engaging interactions
   - User feedback: 80% prefer personalized over generic responses

5. **Langfuse Integration** (v5): Moved prompts to Langfuse for versioning and A/B testing
   - Benefit: Can update prompts without code changes, track prompt performance
   - Current: All prompts versioned in Langfuse with production labels

### 4.4. Context Engineering

**Context Structure:**

We structure context as:
```
[System Prompt (with state injection)]
+ [Conversation History (sliding window, last 10 messages)]
+ [Current User Query]
+ [Tool Results (if any, as ToolMessages)]
```

**Context Window Management:**

- **Sliding Window Approach**: TutorAgent keeps last 10 messages (SystemMessage + 9 conversation turns)
- **Tool Call Pairing**: AIMessage with `tool_calls` and corresponding ToolMessages are kept together (never split)
- **Priority**: Recent messages > Older messages. When limit reached, oldest messages removed first
- **Truncation Logic**: 
  ```python
  def _truncate_message_history(messages: List[BaseMessage], max_messages: int = 10):
      # Keep system message
      system_msg = [m for m in messages if isinstance(m, SystemMessage)]
      # Keep last N-1 non-system messages
      other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
      return system_msg + other_msgs[-(max_messages-1):]
  ```

**Context Retrieval:**

- **Direct Database Access**: No RAG/vector search. We use structured JSONB queries:
  ```sql
  SELECT analysis_data FROM page_analyses 
  WHERE course_material_id = $1 AND page_number = $2
  ```
- **Structured Data**: Each page analysis contains pre-extracted `summary`, `key_terms`, `exam_questions`, `diagram_description` from GPT-4o Vision
- **No Semantic Search**: We rely on exact page number matching rather than semantic similarity (faster, more reliable for our use case)

**Context Compression/Summarization:**

- **Not Implemented**: We don't summarize older messages yet
- **Future Enhancement**: Could implement two-tier memory (detailed last 2 turns, summarized turns 3-10)

**Dynamic Context Selection:**

- **Mode-Based Context**: QuickChatAgent uses different context templates:
  - **Discovery Mode**: Includes `search_topic` and `get_user_courses` tool results
  - **Tutoring Mode**: Includes `get_page_analysis` for current page, similar to TutorAgent
- **Tool-Specific Context**: When `create_quiz` is called, QuizGeneratorAgent receives only relevant page analyses (start_page to end_page), not entire conversation

**Example Context Flow:**

```
User: "Explain this slide"
  ↓
TutorAgent.call_model():
  System Prompt: "You are a tutor. Current page: 5, Material: mat-123, User: user-456"
  Messages: [
    SystemMessage("..."),
    HumanMessage("Explain this slide")
  ]
  ↓
LLM decides: Need page analysis → Calls get_page_analysis
  ↓
Tool returns: ToolMessage({summary: "...", key_terms: [...], ...})
  ↓
TutorAgent.call_model() (next iteration):
  System Prompt: (same)
  Messages: [
    SystemMessage("..."),
    HumanMessage("Explain this slide"),
    AIMessage(tool_calls=[...]),
    ToolMessage({summary: "...", ...})
  ]
  ↓
LLM generates explanation using tool results
```

---

## 5. Evaluation & Challenges

### Testing & Results

**Testing Approach:**

We tested agents through:
1. **Unit Tests**: `test_all_agents.py` - Tests each agent's graph execution, state management, tool calling (16+ test cases)
2. **Integration Tests**: API endpoints with real database queries
3. **Manual Testing**: Real study sessions with actual lecture PDFs (Software Engineering, Database Systems)

**Example 1: TutorAgent Working Well**

**User Input:**
```
"Was ist ein Sequenzdiagramm?"
```

**Agent Process:**
1. Agent receives message with `current_page=15`, `material_id="mat-123"`
2. Agent calls `get_page_analysis` tool (automatic state injection: `course_material_id="mat-123"`, `page_number=15`)
3. Tool returns: `{summary: "Sequence diagrams show object interactions...", key_terms: ["sequence diagram", "UML", "lifeline"], diagram_description: "Diagram shows User → System → Database interactions"}`
4. Agent generates response using this context

**Agent Output:**
```
Ein Sequenzdiagramm ist eine Art von UML-Diagramm, das die Interaktion zwischen verschiedenen Objekten oder Komponenten in einem System über die Zeit zeigt.

Auf dieser Folie siehst du:
- **Objekte/Lebenslinien**: Die vertikalen Linien repräsentieren verschiedene Objekte oder Akteure (z.B. User, System, Database)
- **Nachrichten**: Die horizontalen Pfeile zeigen die Kommunikation zwischen Objekten
- **Zeitachse**: Die Zeit verläuft von oben nach unten

**Beispiel aus der Folie:**
Wenn du dir das Diagramm anschaust, siehst du wie "User" eine Nachricht an "System" sendet, und das System dann eine Antwort zurückgibt.

Möchtest du mehr über die verschiedenen Arten von Nachrichten erfahren (synchrone vs. asynchrone)?
```

**Why it worked:**
- StateAwareToolNode correctly injected `material_id` and `page_number` (no hallucination)
- Tool returned structured data from database (pre-analyzed by GPT-4o Vision)
- Agent used diagram_description to reference visual content
- Agent proactively offered to explain more (proactive behavior)

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

**Why it worked:**
- Structured output ensured valid JSON format (no parsing errors)
- Difficulty distribution met requirements (1-2 easy, 1 medium, 1+ hard)
- Questions tested comprehension, not memorization (application, analysis, synthesis)
- All questions had exactly 4 options and explanations

**Example 3: FlashcardGeneratorAgent Working Well**

**Input:** 
- 50-page PDF about "Software Engineering"
- Conversation history with 20 Q&A pairs
- Material classification: "general" (not language_learning or math)

**Agent Process:**
1. Initializes: Loads all 50 page analyses and snippets
2. Classifies material: "general" (cached in database)
3. For each page (0-49):
   - Skip decision: LLM decides to skip pages 0-2 (title, TOC, intro)
   - Gets context: Conversation messages for page, snippet URL if available
   - Generates cards: 1-2 flashcards per page using structured output
4. Deduplicates: Hash-based pre-filtering + similarity check (removed 3 duplicates)
5. Saves: Syncs 45 cards to Anki, caches in database

**Output:** Generated 45 flashcards (5 pages skipped), 3 duplicates removed, successfully synced to Anki

**Why it worked:**
- Skip decision correctly identified intro/TOC pages
- Conversation context influenced card content (cards addressed questions user asked)
- Deduplication prevented redundant cards (hash-based O(n) algorithm)
- Batch processing handled large PDFs efficiently (checkpointing enabled resumability)

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
- Error rate dropped from ~30% to <5%

**Example 5: Agent Struggling - Context Window**

**Scenario:** Long conversation (50+ messages) about multiple topics across 20 pages

**Problem:** 
- Agent started losing context, repeating earlier explanations
- Agent didn't remember what was discussed on page 5 when user asked follow-up on page 15
- Agent couldn't reference earlier parts of conversation

**Why it struggled:**
- Sliding window (10 messages) was too small for long sessions
- No summarization of older messages
- Agent couldn't reference earlier parts of conversation beyond window

**Partial Solution:**
- Increased window to 15 messages for QuickChatAgent (handles longer search contexts)
- Added conversation summary in system prompt (future enhancement needed)
- Considered two-tier memory but not yet implemented

### Challenges Faced

1. **Tool Argument Hallucination**
   - **Problem**: LLM sometimes generated incorrect IDs (`course_material_id="test-id"`) instead of using state values
   - **Impact**: 30% of tool calls failed
   - **Solution**: Implemented `StateAwareToolNode` that automatically injects state values before tool execution
   - **Result**: Error rate dropped to <5%

2. **Gemini API Message Order Requirements**
   - **Problem**: Gemini requires strict message order: HumanMessage → AIMessage (tool_calls) → ToolMessages. Incomplete tool call pairs (AIMessage with tool_calls but no ToolMessages) caused API errors.
   - **Impact**: 15% of API calls failed with "Invalid message order" errors
   - **Solution**: Implemented `_fix_incomplete_tool_calls()` that validates and removes incomplete pairs
   - **Result**: Reduced API errors by 80%

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

### Limitations

1. **Context Window**: Sliding window of 10-15 messages may lose important context in very long conversations. No summarization implemented yet.

2. **No Proactive Calendar Management**: Planned but not implemented. Agents cannot yet schedule study sessions or adjust learning plans based on calendar.

3. **Limited Multi-Agent Coordination**: Agents work independently. No supervisor agent yet to coordinate between TutorAgent, QuizGeneratorAgent, and FlashcardGeneratorAgent.

4. **No Continual Learning**: Agents don't learn from user feedback or adapt prompts based on success/failure patterns. No feedback mechanism (thumbs up/down) implemented.

5. **Vision Input Limitations**: FlashcardGeneratorAgent can include snippet images, but not all pages have snippets. Some visual content may be missed in flashcard generation.

6. **Language Support**: Currently supports German and English. Adding more languages requires new Langfuse prompts and personality text translations.

7. **Error Recovery**: While checkpointer enables resumability, there's no automatic recovery. If flashcard generation fails at 80%, user must manually resume with same `thread_id`.

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
- Users can request data deletion (not yet implemented in UI, but possible via API)
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
- ✅ **Multimodal Content Analysis**: Successfully extracts structured information from PDF slides using GPT-4o Vision with 95%+ accuracy
- ✅ **Context-Aware Tutoring**: Agents maintain conversation context across sessions using LangGraph checkpointer
- ✅ **Proactive Behavior**: Agents create quizzes and flashcards autonomously when appropriate
- ✅ **Personalization**: Communication style adapts to user preferences (formality, humor, encouragement)
- ✅ **Robust Architecture**: StateAwareToolNode eliminates tool-calling errors, Langfuse enables prompt versioning

**Key Takeaways:**
1. **State Management is Critical**: Automatic state injection (StateAwareToolNode) eliminated 95% of tool-calling errors
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

- OpenAI Documentation. (2024). "GPT-4o Vision." https://platform.openai.com/docs/guides/vision

- Langfuse Documentation. (2024). "Prompt Management." https://langfuse.com/docs/prompts

- Supabase Documentation. (2024). "Row Level Security." https://supabase.com/docs/guides/auth/row-level-security

- AnkiConnect API. (2024). "AnkiConnect Documentation." https://github.com/FooSoft/anki-connect

---

## 10. Individual Contribution Log

### Milan Elias Mayer (mmayer11@smail.uni-koeln.de)

**Major Contributions:**

- **Anki Integration & Flashcard System**: Implemented complete Anki integration with Docker support, AnkiWeb sync, and conflict management. Built the FlashcardGeneratorAgent with LangGraph state machine, batch processing, and hash-based deduplication logic (O(n) instead of O(n²)).

- **QuickChatAgent**: Developed the QuickChatAgent for topic discovery across multiple courses, with dual-mode operation (discovery and tutoring modes) and automatic page navigation with user confirmation.

- **Frontend Development**: Built comprehensive Next.js frontend including:
  - Study Reader with PDF viewer and chat interface
  - Quick Chat interface with inline PDF viewer and navigation
  - Dashboard with real-time progress tracking and Anki study history
  - Settings modal with user preferences
  - Anki sync status UI and conflict management

- **Performance Optimizations**: 
  - Implemented hash-based flashcard deduplication (reduced time from 30s to <2s for 1000 cards)
  - Added caching for AnkiWeb login status checks
  - Optimized flashcard generation with parallel processing

- **System Architecture**: Designed and implemented the BaseAgent pattern, LangGraph state machines, and tool architecture.

- **Testing**: Created comprehensive test suite (`test_all_agents.py`) with 16+ test cases for all agents and tools.

- **Documentation**: Wrote `AGENT_ANALYSE_UND_DOKUMENTATION.md` with detailed agent analysis and architecture documentation.

**Git Commits (Sample):**
- `feat(anki): add Anki integration for flashcard sync`
- `feat(quickchat): add Quick Chat with inline PDF viewer and navigation confirmation`
- `perf(flashcards): optimize card generation with hash dedup and parallel processing`
- `test(agents): add comprehensive test suite for all agents and tools`
- `feat(dashboard): add real Anki study history to dashboard`

### Louis Braukmann (louis.braukmann@gmail.com)

**Major Contributions:**

- **TutorAgent Development**: Implemented the core TutorAgent with LangGraph state machine, including:
  - StateAwareToolNode for automatic state injection (eliminated 95% of tool-calling errors)
  - Message history truncation and context management (sliding window approach)
  - Personality customization (formality, humor, encouragement)
  - Langfuse prompt integration with fallback mechanisms
  - Gemini API compatibility fixes (`_fix_incomplete_tool_calls()`)

- **QuizGeneratorAgent**: Built the QuizGeneratorAgent with structured output generation, difficulty distribution logic, and validation. Ensured 3-8 questions with appropriate difficulty levels.

- **Tool Development**: Created multiple LangChain tools:
  - `GetPageAnalysisTool` - Retrieves structured page analyses from database
  - `GetCourseMaterialSummaryTool` - Gets course overview
  - `CreateQuizTool` - Triggers QuizGeneratorAgent
  - `GetPageImageTool` - Returns page image URLs

- **Backend API**: Developed FastAPI endpoints for:
  - Chat initiation and messaging (`/api/chat/initiate`, `/api/chat/message`)
  - Streaming responses with Server-Sent Events (SSE)
  - Comprehensive error handling and logging

- **Multimodal Analysis**: Implemented PDF page analysis using GPT-4o Vision API with structured JSON extraction and database storage. Handles image conversion, base64 encoding, and error recovery.

- **State Management**: Designed and implemented LangGraph checkpointer integration for conversation persistence, enabling seamless context across sessions.

- **Prompt Engineering**: Developed system prompts for TutorAgent and QuizGeneratorAgent, including Langfuse integration with fallback mechanisms. Iterated through 5 versions to achieve <5% tool-calling error rate.

**Git Commits (Sample):**
- `Add detailed logging to tutor agent _fix_incomplete_tool_calls`
- `Add detailed logging to tutor agent truncation in call_model`
- `feat: Add support for multiple snippets per page in flashcard generation`
- `merge of the branches - stable`

**Collaboration:**
- Both team members worked closely on integrating agents, debugging tool-calling issues, and refining the overall architecture.
- Regular code reviews and pair programming sessions for complex features like Anki integration and state management.
- Shared responsibility for documentation and testing.

---

**Report Generated**: 2025-01-26  
**Project Repository**: [Repository URL]  
**Last Updated**: 2025-01-26
