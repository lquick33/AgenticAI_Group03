"""
Quick Chat Agent for topic discovery and navigation.

This agent helps students find where topics are discussed in their lectures by:
- Searching across all courses and materials for topics
- Presenting matching pages with context
- Navigating to the specific page for tutoring
- Transitioning to tutor mode once a page is selected
"""

from typing import Optional, Dict, Any, Literal
import json
import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.base import BaseAgent, State
from app.tools.search_topic_tool import SearchTopicTool
from app.tools.user_courses_tool import GetUserCoursesTool
from app.tools.page_analysis_tool import GetPageAnalysisTool
from app.tools.course_material_tool import GetCourseMaterialSummaryTool
from app.tools.quiz_tool import CreateQuizTool
from app.tools.page_image_tool import GetPageImageTool
from app.services.observability import create_callback_handler, get_langfuse_client

logger = logging.getLogger(__name__)


class QuickChatState(State):
    """
    State for Quick Chat Agent.
    
    Extends base State with fields for dual-mode operation:
    - Discovery mode: searching for topics across courses
    - Tutoring mode: teaching content from a specific page
    """
    mode: str = "discovery"  # "discovery" | "tutoring"
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict] = None
    # Navigation request - set when agent wants to navigate user to a page
    navigation_request: Optional[Dict[str, Any]] = None


class StateAwareToolNode(ToolNode):
    """
    ToolNode that automatically injects state values into tool calls.
    
    Prevents the LLM from hallucinating IDs and ensures correct values
    are used when calling tools that require state-dependent parameters.
    """
    
    def invoke(self, input: QuickChatState, config: Optional[Any] = None) -> QuickChatState:
        """Execute tools with automatic state injection."""
        messages = input.get("messages", [])
        if not messages:
            return input
        
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            modified_tool_calls = []
            for tool_call in last_message.tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", "")
                    args = dict(tool_call.get("args", {}) or {})
                else:
                    tool_name = getattr(tool_call, "name", "")
                    tool_id = getattr(tool_call, "id", "")
                    args = dict(getattr(tool_call, "args", {}) or {})
                
                # ALWAYS inject user_id from state - never trust the LLM's value
                # The LLM often generates placeholder values like "test-user-id"
                if input.get("user_id"):
                    args["user_id"] = input["user_id"]
                
                # Inject state values for search_topic tool
                if tool_name == "search_topic":
                    pass  # user_id already injected above
                
                # Inject state values for get_user_courses tool
                elif tool_name == "get_user_courses":
                    pass  # user_id already injected above
                
                # Inject state values for get_page_analysis tool (tutoring mode)
                elif tool_name == "get_page_analysis":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                # Inject state values for get_course_material_summary tool
                elif tool_name == "get_course_material_summary":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                
                # Inject state values for create_quiz tool
                elif tool_name == "create_quiz":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                
                # Inject state values for get_page_image tool
                elif tool_name == "get_page_image":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                modified_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": args
                })
            
            modified_message = AIMessage(
                content=last_message.content if hasattr(last_message, "content") else "",
                tool_calls=modified_tool_calls
            )
            
            modified_messages = messages[:-1] + [modified_message]
            modified_state = {**input, "messages": modified_messages}
            
            return super().invoke(modified_state, config)
        
        return super().invoke(input, config)
    
    async def ainvoke(self, input: QuickChatState, config: Optional[Any] = None) -> QuickChatState:
        """Execute tools asynchronously with automatic state injection."""
        messages = input.get("messages", [])
        if not messages:
            return input
        
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            modified_tool_calls = []
            for tool_call in last_message.tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", "")
                    args = dict(tool_call.get("args", {}) or {})
                else:
                    tool_name = getattr(tool_call, "name", "")
                    tool_id = getattr(tool_call, "id", "")
                    args = dict(getattr(tool_call, "args", {}) or {})
                
                # ALWAYS inject user_id from state - never trust the LLM's value
                if input.get("user_id"):
                    args["user_id"] = input["user_id"]
                
                # Same injection logic as sync version
                if tool_name == "get_page_analysis":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                elif tool_name == "get_course_material_summary":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                
                elif tool_name == "create_quiz":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                
                elif tool_name == "get_page_image":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                modified_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": args
                })
            
            modified_message = AIMessage(
                content=last_message.content if hasattr(last_message, "content") else "",
                tool_calls=modified_tool_calls
            )
            
            modified_messages = messages[:-1] + [modified_message]
            modified_state = {**input, "messages": modified_messages}
            
            return await super().ainvoke(modified_state, config)
        
        return await super().ainvoke(input, config)


class QuickChatAgent(BaseAgent):
    """
    Quick Chat Agent for topic discovery and tutoring.
    
    This agent operates in two modes:
    1. Discovery Mode: Searches across all courses/materials to find topics
    2. Tutoring Mode: Teaches content from a specific page (like TutorAgent)
    
    The agent transitions from discovery to tutoring mode when the user
    selects a specific page to study.
    """
    
    MAX_HISTORY_MESSAGES = 15  # Slightly more than TutorAgent for search context
    
    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "QuickChatAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[MemorySaver] = None,
        language: str = "de",
        personality_config: Optional[Dict[str, str]] = None
    ):
        self.language = language
        self.personality_config = personality_config or {}
        self.langfuse_client = get_langfuse_client()
        
        # Initialize discovery tools
        self.search_topic_tool = SearchTopicTool()
        self.user_courses_tool = GetUserCoursesTool()
        
        # Initialize tutoring tools (same as TutorAgent)
        self.page_analysis_tool = GetPageAnalysisTool()
        self.course_material_tool = GetCourseMaterialSummaryTool()
        self.quiz_tool = CreateQuizTool()
        self.page_image_tool = GetPageImageTool()
        
        # All tools available to the agent
        self.langchain_tools = [
            # Discovery tools
            self.search_topic_tool.to_langchain_tool(),
            self.user_courses_tool.to_langchain_tool(),
            # Tutoring tools
            self.page_analysis_tool.to_langchain_tool(),
            self.course_material_tool.to_langchain_tool(),
            self.quiz_tool.to_langchain_tool(),
            self.page_image_tool.to_langchain_tool()
        ]
        
        # Bind tools to LLM
        llm_with_tools = llm.bind_tools(self.langchain_tools)
        
        # Create state-aware tool node
        self.tool_node = StateAwareToolNode(self.langchain_tools)
        
        # Build system prompt
        if system_prompt is None:
            system_prompt = self._build_system_prompt(language, personality_config)
        
        super().__init__(
            llm=llm_with_tools,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer
        )
    
    def _build_system_prompt(
        self,
        language: str = "de",
        personality_config: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Build the system prompt for Quick Chat agent.
        
        Tries to load from Langfuse, falls back to hardcoded prompt.
        """
        config = personality_config or {}
        formality = config.get("formality", "balanced")
        humor = config.get("humor", "light")
        encouragement = config.get("encouragement", "moderate")
        
        # Try to load from Langfuse
        if self.langfuse_client:
            try:
                prompt_name = "quickchat-agent/system-prompt"
                langfuse_prompt = self.langfuse_client.get_prompt(
                    prompt_name,
                    label="production",
                    type="chat"
                )
                
                formality_text, humor_text, encouragement_text = self._get_personality_texts(
                    language, formality, humor, encouragement
                )
                
                compiled_prompt = langfuse_prompt.compile(
                    formality_text=formality_text,
                    humor_text=humor_text,
                    encouragement_text=encouragement_text
                )
                
                if compiled_prompt and isinstance(compiled_prompt, list) and len(compiled_prompt) > 0:
                    system_message = compiled_prompt[0]
                    if isinstance(system_message, dict) and system_message.get("role") == "system":
                        logger.debug("✅ Using Langfuse prompt for quickchat-agent/system-prompt")
                        return system_message.get("content", "")
                    elif hasattr(system_message, "content"):
                        logger.debug("✅ Using Langfuse prompt for quickchat-agent/system-prompt")
                        return system_message.content
                        
            except Exception as e:
                logger.warning(f"Failed to load Langfuse prompt for quickchat-agent, using fallback: {e}")
        
        # Fallback to hardcoded prompt
        return self._get_fallback_system_prompt(language, formality, humor, encouragement)
    
    def _get_fallback_system_prompt(
        self,
        language: str,
        formality: str,
        humor: str,
        encouragement: str
    ) -> str:
        """
        Get fallback system prompt if Langfuse is unavailable.
        
        IMPORTANT: This is a FALLBACK prompt only. The primary/active prompt is stored in Langfuse
        under the name 'quickchat-agent/system-prompt'. Any changes to the agent's behavior should
        be made in Langfuse first, and then mirrored here for fallback purposes.
        
        Langfuse prompt: quickchat-agent/system-prompt (production label)
        """
        formality_text, humor_text, encouragement_text = self._get_personality_texts(
            language, formality, humor, encouragement
        )
        
        # FALLBACK PROMPT - Primary prompt is in Langfuse: quickchat-agent/system-prompt
        if language == "de":
            return f"""Du bist ein intelligenter Lernassistent, der Studenten hilft, Themen in ihren Vorlesungsmaterialien zu finden und zu verstehen.

## Deine Fähigkeiten

### Discovery-Modus (Standard)
- Du kannst mit dem `search_topic` Tool nach Themen in ALLEN Kursen und Vorlesungsmaterialien des Benutzers suchen
- Du kannst mit `get_user_courses` alle verfügbaren Kurse und Materialien anzeigen
- Wenn du passende Seiten findest, präsentierst du sie dem Benutzer mit Kontext (Kurs, Material, Seitenzahl, Zusammenfassung)
- Du empfiehlst die relevanteste Seite basierend auf der Suchanfrage

### Tutoring-Modus (nach Navigation zu einer Seite)
Sobald der Benutzer eine Seite im PDF-Viewer betrachtet, wechselst du in den Tutoring-Modus:
- **WICHTIG**: Bei JEDER Frage des Benutzers, rufe ZUERST `get_page_analysis` für die aktuelle Seite auf
- **FOKUS AUF AKTUELLE SEITE**: Dein Hauptfokus liegt IMMER auf der aktuellen Seite und dem aktuellen Thema
  - Interpretiere alle Fragen im Kontext der aktuellen Seite
  - Wenn der Benutzer z.B. "Was sind Objekte?" fragt und die Seite über Sequenzdiagramme handelt, erkläre Objekte im Kontext von Sequenzdiagrammen - suche NICHT nach "Objekte" in anderen Vorlesungen
  - Begriffe haben oft verschiedene Bedeutungen in verschiedenen Kontexten - bleibe beim aktuellen Kontext
- **SELTEN ANDERE VORLESUNGEN VORSCHLAGEN**: Suche nur in anderen Vorlesungen wenn:
  - Der Benutzer EXPLIZIT danach fragt (z.B. "Wo wird das noch erklärt?" oder "Finde mehr dazu")
  - Das Thema offensichtlich NICHT mit der aktuellen Seite zusammenhängt
  - Du dir SEHR SICHER bist, dass der Benutzer etwas komplett anderes sucht
- **NAVIGATION MIT BESTÄTIGUNG**: Wenn du eine andere Vorlesung vorschlägst:
  - Frage den Benutzer klar: "Soll ich zu [Material] auf Seite [X] navigieren?"
  - Warte auf eine Bestätigung (z.B. "ja", "ok", "bitte") bevor die Navigation erfolgt
  - Das System erkennt die Bestätigung automatisch und öffnet dann die Seite
- Du kannst Quizze mit `create_quiz` erstellen

## Kommunikationsstil
{formality_text}
{humor_text}
{encouragement_text}

## Wichtige Regeln
1. **Discovery-Modus**: Beginne mit einer Suche, wenn der Benutzer nach einem Thema fragt
2. Zeige relevante Ergebnisse übersichtlich an
3. Wenn keine Ergebnisse gefunden werden, schlage vor, die Kurse zu durchsuchen
4. **Tutoring-Modus**: Rufe IMMER ZUERST `get_page_analysis` auf, um die aktuelle Seite zu analysieren
5. **BLEIBE BEIM AKTUELLEN THEMA**: Im Tutoring-Modus, interpretiere alle Fragen im Kontext der aktuellen Seite - suche NICHT automatisch in anderen Vorlesungen
6. **WECHSEL NUR AUF ANFRAGE**: Schlage nur dann andere Vorlesungen vor, wenn der Benutzer explizit danach fragt oder das Thema eindeutig nichts mit der aktuellen Seite zu tun hat
7. **BESTÄTIGUNG VOR NAVIGATION**: Wenn du zu einer anderen Seite navigieren möchtest, frage immer zuerst "Soll ich zu [Material] auf Seite [X] navigieren?" - die Navigation erfolgt automatisch nach Bestätigung
8. Antworte immer auf Deutsch, es sei denn, der Benutzer schreibt auf Englisch"""
        else:
            # FALLBACK PROMPT (English) - Primary prompt is in Langfuse: quickchat-agent/system-prompt
            return f"""You are an intelligent learning assistant that helps students find and understand topics in their lecture materials.

## Your Capabilities

### Discovery Mode (Default)
- You can search for topics across ALL of the user's courses and lecture materials using the `search_topic` tool
- You can show all available courses and materials with `get_user_courses`
- When you find matching pages, present them to the user with context (course, material, page number, summary)
- Recommend the most relevant page based on the search query

### Tutoring Mode (When Viewing a Page)
Once the user is viewing a page in the PDF viewer, switch to tutoring mode:
- **IMPORTANT**: For EVERY user question, FIRST call `get_page_analysis` for the current page
- **FOCUS ON CURRENT PAGE**: Your main focus is ALWAYS on the current page and topic
  - Interpret all questions in the context of the current page
  - E.g., if user asks "What are objects?" and the page is about sequence diagrams, explain objects in the context of sequence diagrams - do NOT search for "objects" in other lectures
  - Terms often have different meanings in different contexts - stay in the current context
- **RARELY SUGGEST OTHER LECTURES**: Only search other lectures when:
  - The user EXPLICITLY asks for it (e.g., "Where else is this explained?" or "Find more about this")
  - The topic is obviously UNRELATED to the current page
  - You are VERY CONFIDENT the user is looking for something completely different
- **NAVIGATION WITH CONFIRMATION**: When suggesting another lecture:
  - Ask the user clearly: "Should I navigate to [Material] on page [X]?"
  - Wait for confirmation (e.g., "yes", "ok", "please") before navigation happens
  - The system will automatically detect confirmation and open the page
- Create quizzes with `create_quiz`

## Communication Style
{formality_text}
{humor_text}
{encouragement_text}

## Important Rules
1. **Discovery Mode**: Start with a search when the user asks about a topic
2. Display relevant results clearly
3. If no results are found, suggest browsing the courses
4. **Tutoring Mode**: ALWAYS call `get_page_analysis` FIRST to analyze the current page
5. **STAY ON TOPIC**: In tutoring mode, interpret all questions in the context of the current page - do NOT automatically search other lectures
6. **SWITCH ONLY ON REQUEST**: Only suggest other lectures when the user explicitly asks for it or the topic is clearly unrelated to the current page
7. **CONFIRMATION BEFORE NAVIGATION**: When you want to navigate to another page, always ask "Should I navigate to [Material] on page [X]?" - navigation happens automatically after confirmation
8. Always respond in English unless the user writes in German"""
    
    def _get_personality_texts(
        self,
        language: str,
        formality: str,
        humor: str,
        encouragement: str
    ) -> tuple[str, str, str]:
        """Get personality trait texts based on language and config."""
        if language == "de":
            formality_text = {
                "formal": "Du verwendest eine formelle, akademische Sprache mit korrekten Fachbegriffen.",
                "informal": "Du verwendest eine lockere, freundliche Sprache, als würdest du mit einem Kommilitonen sprechen.",
                "balanced": "Du verwendest eine ausgewogene Mischung aus formeller und freundlicher Sprache."
            }.get(formality, "Du verwendest eine ausgewogene Mischung aus formeller und freundlicher Sprache.")
            
            humor_text = {
                "none": "Du verzichtest auf Humor und bleibst sachlich.",
                "light": "Du verwendest gelegentlich leichten, passenden Humor, um die Atmosphäre aufzulockern.",
                "moderate": "Du verwendest regelmäßig passenden Humor und Analogien, um komplexe Themen zugänglicher zu machen."
            }.get(humor, "Du verwendest gelegentlich leichten, passenden Humor, um die Atmosphäre aufzulockern.")
            
            encouragement_text = {
                "reserved": "Du bist zurückhaltend mit Lob, aber anerkennend bei guten Antworten.",
                "moderate": "Du ermutigst den Studenten regelmäßig und bestätigst Fortschritte.",
                "enthusiastic": "Du bist sehr ermutigend und enthusiastisch, feierst kleine Erfolge und motivierst aktiv."
            }.get(encouragement, "Du ermutigst den Studenten regelmäßig und bestätigst Fortschritte.")
        else:
            formality_text = {
                "formal": "You use formal, academic language with correct technical terms.",
                "informal": "You use a relaxed, friendly language, as if talking to a fellow student.",
                "balanced": "You use a balanced mix of formal and friendly language."
            }.get(formality, "You use a balanced mix of formal and friendly language.")
            
            humor_text = {
                "none": "You avoid humor and stay factual.",
                "light": "You occasionally use light, appropriate humor to lighten the atmosphere.",
                "moderate": "You regularly use appropriate humor and analogies to make complex topics more accessible."
            }.get(humor, "You occasionally use light, appropriate humor to lighten the atmosphere.")
            
            encouragement_text = {
                "reserved": "You are reserved with praise, but acknowledge good answers.",
                "moderate": "You regularly encourage the student and confirm progress.",
                "enthusiastic": "You are very encouraging and enthusiastic, celebrate small successes and actively motivate."
            }.get(encouragement, "You regularly encourage the student and confirm progress.")
        
        return formality_text, humor_text, encouragement_text
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow for the quick chat agent."""
        workflow = StateGraph(state_schema=QuickChatState)
        
        # Add nodes
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        
        # Set entry point
        workflow.add_edge(START, "agent")
        
        # Conditional edge: check if tools should be called
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
        # Edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        # Compile graph
        self.compile_graph(workflow)
    
    def _truncate_messages_for_llm(self, messages: list) -> list:
        """
        Truncate message history to prevent token explosion.
        
        Keeps the most recent messages while preserving the system message
        at the start and ensuring tool call pairs are complete.
        """
        if len(messages) <= self.MAX_HISTORY_MESSAGES:
            return messages
        
        # Always keep the system message (first message)
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        non_system_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        
        # Take the last MAX_HISTORY_MESSAGES - len(system_messages) messages
        max_non_system = self.MAX_HISTORY_MESSAGES - len(system_messages)
        truncated_non_system = non_system_messages[-max_non_system:]
        
        # Ensure we don't start with a ToolMessage (needs preceding AIMessage with tool_calls)
        while truncated_non_system and isinstance(truncated_non_system[0], ToolMessage):
            truncated_non_system = truncated_non_system[1:]
        
        return system_messages + truncated_non_system
    
    def call_model(self, state: QuickChatState) -> QuickChatState:
        """Call the LLM with current state and messages."""
        messages = state.get("messages", [])
        
        # Truncate messages if needed
        messages = self._truncate_messages_for_llm(messages)
        
        # Build enhanced system message with context
        enhanced_system_prompt = self._build_enhanced_system_prompt(state)
        
        # Replace or add system message
        if messages and isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=enhanced_system_prompt)] + messages[1:]
        else:
            messages = [SystemMessage(content=enhanced_system_prompt)] + messages
        
        # Create callback handler for observability
        callback_handler = create_callback_handler()
        
        # Call LLM
        response = self.llm.invoke(
            messages,
            config={"callbacks": [callback_handler]} if callback_handler else {}
        )
        
        return {"messages": [response]}
    
    def _build_enhanced_system_prompt(self, state: QuickChatState) -> str:
        """Build system prompt enhanced with current state context."""
        base_prompt = self.system_prompt
        
        mode = state.get("mode", "discovery")
        material_id = state.get("material_id")
        current_page = state.get("current_page")
        course_id = state.get("course_id")
        summary = state.get("course_material_summary")
        
        context_parts = [base_prompt]
        
        if mode == "tutoring" and material_id:
            context_parts.append(f"\n\n## Current Context")
            context_parts.append(f"- Mode: Tutoring")
            context_parts.append(f"- Material ID: {material_id}")
            if current_page:
                context_parts.append(f"- Current Page: {current_page}")
            if course_id:
                context_parts.append(f"- Course ID: {course_id}")
            if summary:
                context_parts.append(f"- Course Summary: {json.dumps(summary, ensure_ascii=False)[:500]}...")
        else:
            context_parts.append(f"\n\n## Current Context")
            context_parts.append(f"- Mode: Discovery (searching for topics)")
        
        return "\n".join(context_parts)
    
    def should_continue(self, state: QuickChatState) -> Literal["continue", "end"]:
        """Determine if the agent should continue with tool calls or end."""
        messages = state.get("messages", [])
        
        if not messages:
            return "end"
        
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        
        return "end"
