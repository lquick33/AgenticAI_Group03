"""
Tutor Agent for study sessions.

This agent helps students understand lecture materials by:
- Retrieving page analysis data from the database
- Explaining slide content
- Answering questions about the material
- Providing context-aware tutoring
"""

from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
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


class TutorAgent(BaseAgent):
    """
    Tutor Agent for study sessions.
    
    This agent uses the GetPageAnalysisTool to retrieve slide information
    and provides contextual tutoring based on the lecture material.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "TutorAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[MemorySaver] = None
    ):
        # Initialize tool
        self.page_analysis_tool = GetPageAnalysisTool()
        self.langchain_tool = self.page_analysis_tool.to_langchain_tool()
        
        # Bind tool to LLM
        llm_with_tools = llm.bind_tools([self.langchain_tool])
        
        # Create tool node
        self.tool_node = ToolNode([self.langchain_tool])
        
        # Default system prompt
        default_system_prompt = (
            "You are a helpful and patient tutor for university students. "
            "Your role is to help students understand lecture materials by:\n"
            "- Explaining slide content in a clear and engaging way\n"
            "- Answering questions about the material\n"
            "- Providing examples and analogies when helpful\n"
            "- Encouraging active learning\n\n"
            "When a student navigates to a new slide, use the get_page_analysis tool "
            "to retrieve information about that slide, then greet the student and "
            "explain the key concepts on the slide. Be conversational and supportive."
        )
        
        super().__init__(
            llm=llm_with_tools,
            name=name,
            system_prompt=system_prompt or default_system_prompt,
            checkpointer=checkpointer
        )
    
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
        Call LLM with current messages.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with LLM response
        """
        messages = state["messages"]
        
        # Ensure system message is present
        messages_for_llm = self.add_system_message(messages)
        
        # Call LLM
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
