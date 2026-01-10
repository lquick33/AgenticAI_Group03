"""
Tool-using agent that can decide when and how to use tools.
"""

from typing import List, Optional, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver
from agentic_ai.agents.base import BaseAgent, State


class ToolAgent(BaseAgent):
    """
    An agent that can use tools to accomplish tasks.
    
    This agent demonstrates how to integrate tools with LangGraph agents,
    including tool calling, execution, and response generation.
    """
    
    def __init__(
        self, 
        llm: BaseChatModel,
        tools: List[BaseTool],
        name: str = "ToolAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None
    ):
        self.tools = tools
        self.tool_node = ToolNode(tools)
        
        default_prompt = (
            "You are a helpful AI assistant with access to various tools. "
            "Use the available tools when they can help answer the user's question or complete their request. "
            "Always explain what you're doing and provide clear, helpful responses."
        )
        
        super().__init__(
            llm=llm.bind_tools(tools),  # Bind tools to the LLM
            name=name,
            system_prompt=system_prompt or default_prompt,
            checkpointer=checkpointer
        )
    
    def _build_graph(self) -> None:
        """Build a graph that can handle tool calling."""
        workflow = StateGraph(State)
        
        # Add nodes
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        # Compile the graph (uses checkpointer if provided)
        self.compile_graph(workflow)
    
    def call_model(self, state: State) -> State:
        """
        Call the language model with the current messages.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with model response
        """
        messages = state["messages"]
        
        # For Gemini with tools, we need to handle system messages differently
        # Don't add SystemMessage to messages list for Gemini with bound tools
        # Instead, prepend system prompt to first human message
        from langchain_core.messages import HumanMessage, SystemMessage
        
        has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
        
        if not has_system_message and self.system_prompt:
            # Find the first HumanMessage and prepend system prompt to it
            modified_messages = []
            system_prepended = False
            
            for msg in messages:
                if isinstance(msg, HumanMessage) and not system_prepended:
                    # Prepend system prompt to first human message
                    new_content = f"{self.system_prompt}\n\nUser: {msg.content}"
                    modified_messages.append(HumanMessage(content=new_content))
                    system_prepended = True
                else:
                    modified_messages.append(msg)
            
            messages_to_use = modified_messages
        else:
            messages_to_use = messages
        
        # Get response from LLM
        response = self.llm.invoke(messages_to_use)
        
        # Update state
        return State(
            messages=messages + [response],
            next_step=None
        )
    
    def should_continue(self, state: State) -> str:
        """
        Determine whether to continue with tool calling or end.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" if there are tool calls to execute, "end" otherwise
        """
        last_message = state["messages"][-1]
        
        # If the last message has tool calls, continue to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        else:
            return "end"
    
    def process_message(self, state: State) -> State:
        """
        This method is required by the base class but not used in this implementation.
        The tool agent uses call_model instead.
        """
        return self.call_model(state)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return [tool.name for tool in self.tools]
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of available tools."""
        return {tool.name: tool.description for tool in self.tools}


# Example usage and testing
if __name__ == "__main__":
    # This would normally use real tools and LLM, but here's how you'd set it up:
    from dotenv import load_dotenv
    from langchain.chat_models import init_chat_model
    from langgraph.checkpoint.memory import InMemorySaver
    from agentic_ai.tools import CalculatorTool
    
    load_dotenv()

    # Initialize LLM
    llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai")

    memory = InMemorySaver()
    
    # Create tools
    calculator = CalculatorTool()
    tools = [calculator.to_langchain_tool()]
    
    # Create agent
    agent = ToolAgent(llm, tools, name="ToolBot", checkpointer=memory)
    
    # Test the agent
    config = {"configurable": {"thread_id": "trace_example"}}
    response = agent.run("What is 25 * 4 + 10?", config)

    print("Full Conversation History:")
    print("=" * 50)
    history = agent.get_conversation_history(config)

    for i, msg in enumerate(history):
        print(f"\n{i+1}. {msg.__class__.__name__}:")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"   Tool Calls: {msg.tool_calls}")
        if hasattr(msg, 'tool_call_id'):
            print(f"   Tool Call ID: {msg.tool_call_id}")
        print(f"   Content: {str(msg.content)[:200]}..." if len(str(msg.content)) > 200 else f"   Content: {msg.content}")