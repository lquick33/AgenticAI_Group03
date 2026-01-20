"""
Tutor Agent for study sessions.

This agent helps students understand lecture materials by:
- Retrieving page analysis data from the database
- Explaining slide content
- Answering questions about the material
- Providing context-aware tutoring
"""

from typing import Optional, Dict, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.agents.base import BaseAgent, State
from app.tools.page_analysis_tool import GetPageAnalysisTool


class TutorState(State):
    """
    State for Tutor Agent.
    
    Extends base State with additional fields for tutor-specific context.
    """
    current_page: Optional[int] = None
    material_id: Optional[str] = None
    user_id: Optional[str] = None


class StateAwareToolNode(ToolNode):
    """
    ToolNode that automatically injects state values into tool calls.
    
    This prevents the LLM from hallucinating IDs and ensures the correct
    values (material_id, current_page, user_id) are always used when
    calling tools.
    """
    
    def __call__(self, state: TutorState) -> TutorState:
        """
        Execute tools with automatic state injection.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tool results
        """
        messages = state["messages"]
        if not messages:
            return state
        
        last_message = messages[-1]
        
        # Check if last message has tool calls
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Inject state values into tool calls
            for tool_call in last_message.tool_calls:
                if hasattr(tool_call, 'args') or isinstance(tool_call, dict):
                    # Handle both dict and object-style tool calls
                    args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                    
                    # Map material_id (State) to course_material_id (Tool argument)
                    if "course_material_id" not in args and state.get("material_id"):
                        if isinstance(tool_call, dict):
                            tool_call["args"] = tool_call.get("args", {})
                            tool_call["args"]["course_material_id"] = state["material_id"]
                        else:
                            if not hasattr(tool_call, "args"):
                                tool_call.args = {}
                            tool_call.args["course_material_id"] = state["material_id"]
                    
                    # Inject page_number from state
                    if "page_number" not in args and state.get("current_page"):
                        if isinstance(tool_call, dict):
                            tool_call["args"] = tool_call.get("args", {})
                            tool_call["args"]["page_number"] = state["current_page"]
                        else:
                            if not hasattr(tool_call, "args"):
                                tool_call.args = {}
                            tool_call.args["page_number"] = state["current_page"]
                    
                    # Inject user_id from state
                    if "user_id" not in args and state.get("user_id"):
                        if isinstance(tool_call, dict):
                            tool_call["args"] = tool_call.get("args", {})
                            tool_call["args"]["user_id"] = state["user_id"]
                        else:
                            if not hasattr(tool_call, "args"):
                                tool_call.args = {}
                            tool_call.args["user_id"] = state["user_id"]
        
        # Call parent implementation to execute tools
        return super().__call__(state)


class TutorAgent(BaseAgent):
    """
    Tutor Agent for study sessions.
    
    This agent uses the GetPageAnalysisTool to retrieve slide information
    and provides contextual tutoring based on the lecture material.
    
    The agent can be personalized with:
    - Language: Communication language (default: "de")
    - Personality: Character traits (formality, humor, encouragement)
    """
    
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
        
        # Initialize tool
        self.page_analysis_tool = GetPageAnalysisTool()
        self.langchain_tool = self.page_analysis_tool.to_langchain_tool()
        
        # Bind tool to LLM
        llm_with_tools = llm.bind_tools([self.langchain_tool])
        
        # Create state-aware tool node
        self.tool_node = StateAwareToolNode([self.langchain_tool])
        
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
        
        Args:
            language: Language code (e.g., "de", "en")
            personality_config: Dict with personality traits:
                - formality: "formal" | "informal" | "balanced"
                - humor: "none" | "light" | "moderate"
                - encouragement: "reserved" | "moderate" | "enthusiastic"
        
        Returns:
            Personalized system prompt string
        """
        config = personality_config or {}
        formality = config.get("formality", "balanced")
        humor = config.get("humor", "light")
        encouragement = config.get("encouragement", "moderate")
        
        # Language-specific base role
        if language == "de":
            role_base = (
                "Du bist ein persönlicher Professor für Universitätsstudenten. "
                "Du erklärst komplexe Konzepte auf studentennahem und verständlichem Niveau, "
                "als wärst du ein hilfreicher Tutor, der sich Zeit für jeden Studenten nimmt."
            )
            teaching_style = (
                "DEINE LEHRMETHODE (Sokratische Methode):\n"
                "- Stelle Fragen BEVOR du erklärst (prüfe das Verständnis zuerst)\n"
                "- Verwende Analogien und Beispiele aus dem Alltag\n"
                "- Zerlege komplexe Konzepte in kleinere Schritte\n"
                "- Ermutige aktives Denken: 'Was denkst du passiert, wenn...?'\n"
                "- Passe die Erklärungstiefe an die Antworten des Studenten an\n"
                "- Vermeide Monologe - halte Erklärungen kurz (2-3 Sätze)\n"
            )
        else:  # Default to English
            role_base = (
                "You are a personal professor for university students. "
                "You explain complex concepts at a student-friendly and understandable level, "
                "like a helpful tutor who takes time for each student."
            )
            teaching_style = (
                "YOUR TEACHING METHOD (Socratic Method):\n"
                "- Ask questions BEFORE explaining (check understanding first)\n"
                "- Use analogies and examples from everyday life\n"
                "- Break complex concepts into smaller steps\n"
                "- Encourage active thinking: 'What do you think happens if...?'\n"
                "- Adapt your explanation depth to the student's responses\n"
                "- Avoid monologues - keep explanations concise (2-3 sentences)\n"
            )
        
        # Personality traits
        if language == "de":
            formality_text = {
                "formal": "Du verwendest eine formelle, akademische Sprache mit korrekten Fachbegriffen.",
                "informal": "Du verwendest eine lockere, freundliche Sprache, als würdest du mit einem Kommilitonen sprechen.",
                "balanced": "Du verwendest eine ausgewogene Mischung aus formeller und freundlicher Sprache."
            }.get(formality, "")
            
            humor_text = {
                "none": "Du verzichtest auf Humor und bleibst sachlich.",
                "light": "Du verwendest gelegentlich leichten, passenden Humor, um die Atmosphäre aufzulockern.",
                "moderate": "Du verwendest regelmäßig passenden Humor und Analogien, um komplexe Themen zugänglicher zu machen."
            }.get(humor, "")
            
            encouragement_text = {
                "reserved": "Du bist zurückhaltend mit Lob, aber anerkennend bei guten Antworten.",
                "moderate": "Du ermutigst den Studenten regelmäßig und bestätigst Fortschritte.",
                "enthusiastic": "Du bist sehr ermutigend und enthusiastisch, feierst kleine Erfolge und motivierst aktiv."
            }.get(encouragement, "")
        else:
            formality_text = {
                "formal": "You use formal, academic language with correct technical terms.",
                "informal": "You use a relaxed, friendly language, as if talking to a fellow student.",
                "balanced": "You use a balanced mix of formal and friendly language."
            }.get(formality, "")
            
            humor_text = {
                "none": "You avoid humor and stay factual.",
                "light": "You occasionally use light, appropriate humor to lighten the atmosphere.",
                "moderate": "You regularly use appropriate humor and analogies to make complex topics more accessible."
            }.get(humor, "")
            
            encouragement_text = {
                "reserved": "You are reserved with praise, but acknowledge good answers.",
                "moderate": "You regularly encourage the student and confirm progress.",
                "enthusiastic": "You are very encouraging and enthusiastic, celebrate small successes and actively motivate."
            }.get(encouragement, "")
        
        # Tool usage instructions
        if language == "de":
            tool_instructions = (
                "TOOL-NUTZUNG:\n"
                "- Du kennst immer, welche Folie der Student gerade betrachtet (aus dem Kontext)\n"
                "- Verwende das get_page_analysis Tool, um Folieninhalte abzurufen, wenn nötig\n"
                "- Die Argumente course_material_id, page_number und user_id werden automatisch aus dem Kontext gefüllt\n"
                "- Wenn ein Tool einen Fehler zurückgibt, erkenne dies an und arbeite mit dem, was du weißt\n\n"
            )
            context_awareness = (
                "KONTEXT-BEWUSSTSEIN:\n"
                "- Du erhältst automatisch Informationen über die aktuelle Folie (Seitennummer)\n"
                "- Du kennst die Material-ID und User-ID aus dem Kontext\n"
                "- Wenn ein Student zu einer neuen Folie navigiert, begrüße ihn und biete an, den Inhalt zu erklären\n\n"
            )
        else:
            tool_instructions = (
                "TOOL USAGE:\n"
                "- You always know which slide the student is viewing (from context)\n"
                "- Use the get_page_analysis tool to retrieve slide content when needed\n"
                "- The arguments course_material_id, page_number, and user_id are automatically filled from context\n"
                "- If a tool returns an error, acknowledge it and work with what you know\n\n"
            )
            context_awareness = (
                "CONTEXT AWARENESS:\n"
                "- You automatically receive information about the current slide (page number)\n"
                "- You know the material ID and user ID from context\n"
                "- When a student navigates to a new slide, greet them and offer to explain the content\n\n"
            )
        
        # Communication style
        if language == "de":
            communication_style = (
                "KOMMUNIKATIONSSTIL:\n"
                "- Professionell aber freundlich (wie ein hilfreicher Tutor)\n"
                "- Verwende Fachbegriffe, aber erkläre sie beim ersten Mal\n"
                "- Halte Antworten prägnant (2-3 Sätze für Erklärungen, 1-2 für Fragen)\n"
                "- Verwende Emojis sparsam (nur zur Ermutigung: ✅, 💡, 🤔)\n\n"
            )
        else:
            communication_style = (
                "COMMUNICATION STYLE:\n"
                "- Professional but friendly (like a helpful TA)\n"
                "- Use technical terms but explain them when first introduced\n"
                "- Keep responses concise (2-3 sentences for explanations, 1-2 for questions)\n"
                "- Use emojis sparingly (only for encouragement: ✅, 💡, 🤔)\n\n"
            )
        
        # Combine all parts
        prompt_parts = [
            role_base,
            "",
            teaching_style,
            "",
            "CHARAKTEREIGENSCHAFTEN:",
            formality_text,
            humor_text,
            encouragement_text,
            "",
            context_awareness,
            tool_instructions,
            communication_style
        ]
        
        return "\n".join(filter(None, prompt_parts))
    
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
        
        context_str = "\n".join(context_parts) if context_parts else ""
        
        # Ensure system message is present
        messages_for_llm = self.add_system_message(messages)
        
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
        
        # Call LLM with streaming support
        # Note: For token-level streaming, we'll use astream_events in the endpoint
        # For now, we keep invoke for compatibility, but the endpoint will handle streaming
        response = self.llm.invoke(messages_for_llm)
        
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
