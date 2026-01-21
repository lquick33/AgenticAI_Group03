"""
Tutor Agent for study sessions.

This agent helps students understand lecture materials by:
- Retrieving page analysis data from the database
- Explaining slide content
- Answering questions about the material
- Providing context-aware tutoring
"""

from typing import Optional, Dict, Any
import json
import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.base import BaseAgent, State
from app.tools.page_analysis_tool import GetPageAnalysisTool
from app.tools.course_material_tool import GetCourseMaterialSummaryTool
from app.services.observability import create_callback_handler, get_langfuse_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class TutorState(State):
    """
    State for Tutor Agent.
    
    Extends base State with additional fields for tutor-specific context.
    """
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    user_id: Optional[str] = None
    course_material_summary: Optional[dict] = None


class StateAwareToolNode(ToolNode):
    """
    ToolNode that automatically injects state values into tool calls.
    
    This prevents the LLM from hallucinating IDs and ensures the correct
    values (material_id, current_page, user_id) are always used when
    calling tools.
    """
    
    def invoke(self, input: TutorState, config: Optional[Any] = None) -> TutorState:
        """
        Execute tools with automatic state injection.
        
        This overrides the invoke method to inject state values before
        tool execution, ensuring required parameters are always present.
        
        Args:
            input: Current agent state
            config: Optional configuration
            
        Returns:
            Updated state with tool results
        """
        messages = input.get("messages", [])
        if not messages:
            return input
        
        last_message = messages[-1]
        
        # Check if last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Create a modified copy of tool calls with injected state values
            modified_tool_calls = []
            for tool_call in last_message.tool_calls:
                # Get tool call information
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", "")
                    args = dict(tool_call.get("args", {}) or {})
                else:
                    tool_name = getattr(tool_call, "name", "")
                    tool_id = getattr(tool_call, "id", "")
                    args = dict(getattr(tool_call, "args", {}) or {})
                
                # Inject state values for get_page_analysis tool
                if tool_name == "get_page_analysis":
                    # Always inject course_material_id from state if missing
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    
                    # Inject user_id from state if missing
                    if "user_id" not in args or not args.get("user_id"):
                        if input.get("user_id"):
                            args["user_id"] = input["user_id"]
                    
                    # Only inject page_number if not explicitly provided by LLM
                    # (LLM might specify a different page number, like page 30)
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                # Inject state values for get_course_material_summary tool
                elif tool_name == "get_course_material_summary":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "user_id" not in args or not args.get("user_id"):
                        if input.get("user_id"):
                            args["user_id"] = input["user_id"]
                
                # Create modified tool call
                modified_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": args
                })
            
            # Create a new message with modified tool calls
            from langchain_core.messages import AIMessage
            modified_message = AIMessage(
                content=last_message.content if hasattr(last_message, "content") else "",
                tool_calls=modified_tool_calls
            )
            
            # Replace the last message in the state
            modified_messages = messages[:-1] + [modified_message]
            modified_state = {**input, "messages": modified_messages}
            
            # Call parent implementation with modified state
            return super().invoke(modified_state, config)
        
        # No tool calls, call parent implementation as-is
        return super().invoke(input, config)
    
    async def ainvoke(self, input: TutorState, config: Optional[Any] = None) -> TutorState:
        """
        Execute tools asynchronously with automatic state injection.
        
        Args:
            input: Current agent state
            config: Optional configuration
            
        Returns:
            Updated state with tool results
        """
        messages = input.get("messages", [])
        if not messages:
            return input
        
        last_message = messages[-1]
        
        # Check if last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Create a modified copy of tool calls with injected state values
            modified_tool_calls = []
            for tool_call in last_message.tool_calls:
                # Get tool call information
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "")
                    tool_id = tool_call.get("id", "")
                    args = dict(tool_call.get("args", {}) or {})
                else:
                    tool_name = getattr(tool_call, "name", "")
                    tool_id = getattr(tool_call, "id", "")
                    args = dict(getattr(tool_call, "args", {}) or {})
                
                # Inject state values for get_page_analysis tool
                if tool_name == "get_page_analysis":
                    # Always inject course_material_id from state if missing
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    
                    # Inject user_id from state if missing
                    if "user_id" not in args or not args.get("user_id"):
                        if input.get("user_id"):
                            args["user_id"] = input["user_id"]
                    
                    # Only inject page_number if not explicitly provided by LLM
                    # (LLM might specify a different page number, like page 30)
                    if "page_number" not in args or args.get("page_number") is None:
                        if input.get("current_page"):
                            args["page_number"] = input["current_page"]
                
                # Inject state values for get_course_material_summary tool
                elif tool_name == "get_course_material_summary":
                    if "course_material_id" not in args or not args.get("course_material_id"):
                        if input.get("material_id"):
                            args["course_material_id"] = input["material_id"]
                    if "user_id" not in args or not args.get("user_id"):
                        if input.get("user_id"):
                            args["user_id"] = input["user_id"]
                
                # Create modified tool call
                modified_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": args
                })
            
            # Create a new message with modified tool calls
            from langchain_core.messages import AIMessage
            modified_message = AIMessage(
                content=last_message.content if hasattr(last_message, "content") else "",
                tool_calls=modified_tool_calls
            )
            
            # Replace the last message in the state
            modified_messages = messages[:-1] + [modified_message]
            modified_state = {**input, "messages": modified_messages}
            
            # Call parent implementation with modified state
            return await super().ainvoke(modified_state, config)
        
        # No tool calls, call parent implementation as-is
        return await super().ainvoke(input, config)


class TutorAgent(BaseAgent):
    """
    Tutor Agent for study sessions.
    
    This agent uses the GetPageAnalysisTool to retrieve slide information
    and provides contextual tutoring based on the lecture material.
    
    The agent can be personalized with:
    - Language: Communication language (default: "de")
    - Personality: Character traits (formality, humor, encouragement)
    """
    
    # Maximum number of messages to keep in history for LLM calls (sliding window)
    # This prevents token explosion while maintaining conversation context
    MAX_HISTORY_MESSAGES = 10  # SystemMessage + letzte 9 Messages
    
    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "TutorAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[MemorySaver] = None,
        language: str = "de",
        personality_config: Optional[Dict[str, str]] = None
    ):
        # Store configuration
        self.language = language
        self.personality_config = personality_config or {}
        
        # Langfuse client for prompt management
        self.langfuse_client = get_langfuse_client()
        
        # Initialize tools
        self.page_analysis_tool = GetPageAnalysisTool()
        self.course_material_tool = GetCourseMaterialSummaryTool()
        self.langchain_tools = [
            self.page_analysis_tool.to_langchain_tool(),
            self.course_material_tool.to_langchain_tool()
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
        Build a personalized system prompt based on language and personality config.
        Loads prompt from Langfuse.
        
        Args:
            language: Language code (e.g., "de", "en")
            personality_config: Dict with personality traits:
                - formality: "formal" | "informal" | "balanced"
                - humor: "none" | "light" | "moderate"
                - encouragement: "reserved" | "moderate" | "enthusiastic"
        
        Returns:
            Personalized system prompt string
            
        Raises:
            RuntimeError: If Langfuse client is not available or prompt cannot be loaded
        """
        config = personality_config or {}
        formality = config.get("formality", "balanced")
        humor = config.get("humor", "light")
        encouragement = config.get("encouragement", "moderate")
        
        if not self.langfuse_client:
            raise RuntimeError("Langfuse client is not available. Cannot load system prompt.")
        
        try:
            prompt_name = f"tutor-agent/system-prompt-{language}"
            langfuse_prompt = self.langfuse_client.get_prompt(
                prompt_name,
                label="production",
                type="chat"
            )
            
            # Get personality trait texts
            formality_text, humor_text, encouragement_text = self._get_personality_texts(
                language, formality, humor, encouragement
            )
            
            # Compile prompt with variables
            compiled_prompt = langfuse_prompt.compile(
                formality_text=formality_text,
                humor_text=humor_text,
                encouragement_text=encouragement_text
            )
            
            # Extract system message content from compiled chat prompt
            if compiled_prompt and isinstance(compiled_prompt, list) and len(compiled_prompt) > 0:
                system_message = compiled_prompt[0]
                if isinstance(system_message, dict) and system_message.get("role") == "system":
                    logger.debug(f"✅ Using Langfuse prompt for tutor-agent/system-prompt-{language}")
                    return system_message.get("content", "")
                elif hasattr(system_message, "content"):
                    logger.debug(f"✅ Using Langfuse prompt for tutor-agent/system-prompt-{language}")
                    return system_message.content
            
            raise RuntimeError(f"Invalid prompt structure returned from Langfuse for {prompt_name}")
        except Exception as e:
            logger.error(f"Failed to load Langfuse prompt for tutor-agent: {e}")
            raise RuntimeError(f"Cannot load system prompt from Langfuse: {e}") from e
    
    def _get_personality_texts(
        self,
        language: str,
        formality: str,
        humor: str,
        encouragement: str
    ) -> tuple[str, str, str]:
        """
        Get personality trait texts based on language and config.
        
        Returns:
            Tuple of (formality_text, humor_text, encouragement_text)
        """
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
        """Build the LangGraph workflow for the tutor agent."""
        workflow = StateGraph(state_schema=TutorState)
        
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
    
    def call_model(self, state: TutorState) -> TutorState:
        """
        Call LLM with current messages, injecting state context.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with LLM response
        """
        messages = state["messages"]
        
        # Message History Truncation: Nur die letzten N Messages behalten
        # WICHTIG: Nur für LLM-Call filtern, State bleibt unverändert
        # WICHTIG: Alte SystemMessages verwerfen - add_system_message() setzt den aktuellen System-Prompt
        # Dies verhindert doppelte System-Prompts
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        if len(non_system_messages) > self.MAX_HISTORY_MESSAGES:
            # Tool-Call-Paare sicher behandeln: AIMessage mit tool_calls + zugehörige ToolMessages
            # müssen zusammen bleiben, sonst gibt es Fehler beim LLM-Call
            
            # Einfache Strategie: Nehmen wir die letzten N Messages
            # Wenn das erste Message ein AIMessage mit tool_calls ist, prüfen wir ob es vollständig ist
            trimmed_messages = non_system_messages[-self.MAX_HISTORY_MESSAGES:]
            
            # Prüfe ob das erste Message ein AIMessage mit tool_calls ist
            if trimmed_messages and hasattr(trimmed_messages[0], "tool_calls") and trimmed_messages[0].tool_calls:
                # Sammle alle Tool-Call-IDs aus diesem AIMessage
                first_msg = trimmed_messages[0]
                tool_call_ids = set()
                for tc in first_msg.tool_calls:
                    tool_call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tool_call_id:
                        tool_call_ids.add(tool_call_id)
                
                # Prüfe ob alle zugehörigen ToolMessages in trimmed_messages vorhanden sind
                # ToolMessages kommen normalerweise direkt nach dem AIMessage
                found_tool_messages = set()
                for msg in trimmed_messages[1:]:
                    if isinstance(msg, ToolMessage):
                        tool_call_id = getattr(msg, "tool_call_id", None)
                        if tool_call_id in tool_call_ids:
                            found_tool_messages.add(tool_call_id)
                
                # Wenn nicht alle ToolMessages vorhanden sind, entferne das AIMessage
                # (besser ein Message weniger als ein Fehler)
                if found_tool_messages != tool_call_ids:
                    trimmed_messages = trimmed_messages[1:]
                    # Optional: Versuche noch ein Message mehr zu nehmen, wenn möglich
                    if len(non_system_messages) > len(trimmed_messages):
                        # Hole ein Message mehr von hinten
                        additional_msg = non_system_messages[-(self.MAX_HISTORY_MESSAGES + 1)]
                        if not (hasattr(additional_msg, "tool_calls") and additional_msg.tool_calls):
                            # Nur hinzufügen wenn es kein AIMessage mit tool_calls ist
                            trimmed_messages.insert(0, additional_msg)
            
            messages_for_truncation = trimmed_messages
        else:
            # Keine Truncation nötig, aber SystemMessages trotzdem entfernen
            messages_for_truncation = non_system_messages
        
        # Build dynamic context from state
        context_parts = []
        if state.get("current_page"):
            if self.language == "de":
                context_parts.append(f"Aktuelle Folie: Seite {state['current_page']}")
            else:
                context_parts.append(f"Current slide: Page {state['current_page']}")
        
        if state.get("material_id"):
            if self.language == "de":
                context_parts.append(f"Material-ID: {state['material_id']}")
            else:
                context_parts.append(f"Material ID: {state['material_id']}")
        
        # Add course material summary to context if available
        if state.get("course_material_summary"):
            summary = state["course_material_summary"]
            # Format summary nicely
            if isinstance(summary, dict):
                summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
            else:
                summary_text = str(summary)
            
            if self.language == "de":
                context_parts.append(f"\n\nVORLESUNGSÜBERSICHT:\n{summary_text}")
            else:
                context_parts.append(f"\n\nCOURSE OVERVIEW:\n{summary_text}")
        
        context_str = "\n".join(context_parts) if context_parts else ""
        
        # Ensure system message is present
        # add_system_message() fügt den aktuellen System-Prompt hinzu (keine alten SystemMessages)
        messages_for_llm = self.add_system_message(messages_for_truncation)
        
        # #region agent log
        log_path = r"c:\App\AAI\AgenticAI_Group03\.cursor\debug.log"
        try:
            message_structure = []
            for idx, msg in enumerate(messages_for_llm):
                msg_type = type(msg).__name__
                has_tool_calls = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
                tool_call_count = len(msg.tool_calls) if has_tool_calls else 0
                if isinstance(msg, ToolMessage):
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    message_structure.append({
                        "index": idx,
                        "type": msg_type,
                        "tool_call_id": tool_call_id
                    })
                else:
                    message_structure.append({
                        "index": idx,
                        "type": msg_type,
                        "has_tool_calls": has_tool_calls,
                        "tool_call_count": tool_call_count
                    })
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H2",
                    "location": "tutor_agent.py:call_model(before_llm_call)",
                    "message": "Messages prepared for LLM call",
                    "data": {
                        "messageCount": len(messages_for_llm),
                        "messageStructure": message_structure
                    },
                    "timestamp": int(__import__("time").time() * 1000)
                }) + "\n")
        except Exception:
            pass
        # #endregion agent log
        
        # Enhance system message with context if available
        if context_str and messages_for_llm:
            # Find or create system message
            system_message_found = False
            for i, msg in enumerate(messages_for_llm):
                if isinstance(msg, SystemMessage):
                    # Enhance existing system message with context
                    enhanced_content = f"{msg.content}\n\nCONTEXT:\n{context_str}"
                    if self.language == "de":
                        enhanced_content += (
                            "\n\nWICHTIG: Wenn du das get_page_analysis Tool verwendest, werden folgende Argumente "
                            "automatisch aus dem Kontext gefüllt:\n"
                            f"- course_material_id: {state.get('material_id', 'unbekannt')}\n"
                            f"- page_number: {state.get('current_page', 1)}\n"
                            f"- user_id: {state.get('user_id', 'unbekannt')}"
                        )
                    else:
                        enhanced_content += (
                            "\n\nIMPORTANT: When using the get_page_analysis tool, the following arguments "
                            "are automatically filled from context:\n"
                            f"- course_material_id: {state.get('material_id', 'unknown')}\n"
                            f"- page_number: {state.get('current_page', 1)}\n"
                            f"- user_id: {state.get('user_id', 'unknown')}"
                        )
                    messages_for_llm[i] = SystemMessage(content=enhanced_content)
                    system_message_found = True
                    break
            
            # If no system message found, add one with context
            if not system_message_found:
                enhanced_content = f"{self.system_prompt}\n\nCONTEXT:\n{context_str}"
                if self.language == "de":
                    enhanced_content += (
                        "\n\nWICHTIG: Wenn du das get_page_analysis Tool verwendest, werden folgende Argumente "
                        "automatisch aus dem Kontext gefüllt:\n"
                        f"- course_material_id: {state.get('material_id', 'unbekannt')}\n"
                        f"- page_number: {state.get('current_page', 1)}\n"
                        f"- user_id: {state.get('user_id', 'unbekannt')}"
                    )
                else:
                    enhanced_content += (
                        "\n\nIMPORTANT: When using the get_page_analysis tool, the following arguments "
                        "are automatically filled from context:\n"
                        f"- course_material_id: {state.get('material_id', 'unknown')}\n"
                        f"- page_number: {state.get('current_page', 1)}\n"
                        f"- user_id: {state.get('user_id', 'unknown')}"
                    )
                messages_for_llm.insert(0, SystemMessage(content=enhanced_content))
        
        # Create Langfuse callback handler für automatisches Tracking
        # Der CallbackHandler trackt automatisch:
        # - Token Usage (wird aus response_metadata extrahiert)
        # - Model Parameters
        # - Input/Output Messages
        # - Latency
        # - Errors
        callback_handler = create_callback_handler()
        
        # Prepare config with callbacks and metadata
        # In Langfuse SDK v3+, user_id, session_id und metadata werden via config metadata übergeben
        config = {}
        if callback_handler:
            metadata = {
                "langfuse_user_id": state.get("user_id"),
                "langfuse_session_id": state.get("material_id"),  # Use material_id as session
                "material_id": state.get("material_id"),
                "current_page": state.get("current_page"),
                "agent_name": self.name,
                "language": self.language
            }
            config["callbacks"] = [callback_handler]
            config["metadata"] = metadata
            logger.info(f"🟡 Langfuse: Sending LLM call with metadata: user_id={metadata.get('langfuse_user_id')}, session_id={metadata.get('langfuse_session_id')}, material_id={metadata.get('material_id')}, page={metadata.get('current_page')}")
        
        # Validate message ordering before LLM call to prevent Gemini API errors
        # Gemini requires: User -> Assistant (with tool_calls) -> ToolMessages -> (optional) Assistant -> User
        # Check if last message before LLM call is valid
        if messages_for_llm:
            last_msg = messages_for_llm[-1]
            # If last message is an AIMessage with tool_calls, it's invalid - should have ToolMessages after
            if isinstance(last_msg, AIMessage) and hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                # #region agent log
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "pre-fix",
                            "hypothesisId": "H3",
                            "location": "tutor_agent.py:call_model(invalid_last_message)",
                            "message": "Last message is AIMessage with tool_calls - this will cause API error",
                            "data": {
                                "toolCallCount": len(last_msg.tool_calls)
                            },
                            "timestamp": int(__import__("time").time() * 1000)
                        }) + "\n")
                except Exception:
                    pass
                # #endregion agent log
                
                logger.error(
                    "Invalid message sequence: Last message is AIMessage with tool_calls. "
                    "This will cause Gemini API error. Removing incomplete tool call."
                )
                # Remove the last message (incomplete AIMessage with tool_calls)
                messages_for_llm = messages_for_llm[:-1]
        
        # Call LLM with callbacks
        # Der CallbackHandler trackt automatisch Token-Usage, Model Parameters, etc.
        response = self.llm.invoke(messages_for_llm, config=config)
        
        if callback_handler:
            logger.info("🟢 Langfuse: LLM call completed - data tracked by CallbackHandler")
        
        # Optional: Token-Usage für Debugging loggen
        if settings.DEBUG and callback_handler:
            try:
                # Token-Usage wird bereits vom CallbackHandler getrackt
                # Diese Extraktion ist nur für lokales Logging
                if hasattr(response, "response_metadata"):
                    usage_meta = response.response_metadata.get("usage_metadata", {})
                    if usage_meta:
                        logger.info(f"🟢 Langfuse: Token usage tracked - {usage_meta}")
            except Exception:
                pass  # Nicht kritisch wenn Token-Usage nicht extrahiert werden kann
        
        # Return updated state (MessagesState will automatically add the message)
        return {"messages": [response]}
    
    def should_continue(self, state: TutorState) -> str:
        """
        Determine if tools should be called.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" if tools should be called, "end" otherwise
        """
        messages = state["messages"]
        if not messages:
            return "end"
        
        last_message = messages[-1]
        
        # Check if last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        
        return "end"
