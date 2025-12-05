"""
Tool-using agent that can decide when and how to use tools.
"""

import asyncio
from typing import List, Optional, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver
from agentic_ai.agents.base import BaseAgent, State


def create_async_tool_node(tools: List[BaseTool]):
    """
    Create a tool node that handles both sync and async tools.
    
    This is necessary because some tools (like MCP tools) are async-only
    and don't support synchronous invocation.
    
    Args:
        tools: List of tools to execute
        
    Returns:
        A function that can be used as a graph node
    """
    tool_map = {tool.name: tool for tool in tools}
    
    async def async_tool_node(state: State) -> State:
        """
        Execute tools, handling both sync and async tools.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tool results
        """
        messages = state["messages"]
        last_message = messages[-1]
        
        # Extract tool calls from the last message
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return state
        
        tool_messages = []
        
        for tool_call in last_message.tool_calls:
            # Handle both dict and object formats for tool calls
            if isinstance(tool_call, dict):
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_call_id = tool_call.get("id")
            else:
                tool_name = getattr(tool_call, "name", None)
                tool_args = getattr(tool_call, "args", {})
                tool_call_id = getattr(tool_call, "id", None)
            
            if not tool_name or tool_name not in tool_map:
                error_msg = f"Tool {tool_name} not found" if tool_name else "Tool name not provided"
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {error_msg}",
                        name=tool_name or "unknown",
                        tool_call_id=tool_call_id,
                        status="error"
                    )
                )
                continue
            
            tool = tool_map[tool_name]
            
            try:
                # Ensure tool_args is a dict
                if not isinstance(tool_args, dict):
                    tool_args = {}
                
                # Check if tool supports async invocation
                # Priority: ainvoke > _arun > invoke (in thread) > _run (in thread)
                if hasattr(tool, 'ainvoke'):
                    # Async tool - use ainvoke (accepts dict directly)
                    result = await tool.ainvoke(tool_args)
                elif hasattr(tool, '_arun'):
                    # Async tool with _arun method (needs unpacked kwargs)
                    result = await tool._arun(**tool_args)
                elif hasattr(tool, 'invoke'):
                    # Sync tool - use invoke in a thread to avoid blocking
                    result = await asyncio.to_thread(tool.invoke, tool_args)
                elif hasattr(tool, '_run'):
                    # Sync tool with _run method (needs unpacked kwargs)
                    result = await asyncio.to_thread(tool._run, **tool_args)
                else:
                    # Fallback: try direct call
                    if hasattr(tool, 'run'):
                        if asyncio.iscoroutinefunction(tool.run):
                            result = await tool.run(**tool_args)
                        else:
                            result = await asyncio.to_thread(tool.run, **tool_args)
                    else:
                        raise ValueError(f"Tool {tool_name} does not have a callable method")
                
                # Convert result to string if needed
                if not isinstance(result, str):
                    result = str(result)
                
                tool_messages.append(
                    ToolMessage(
                        content=result,
                        name=tool_name,
                        tool_call_id=tool_call_id
                    )
                )
            except Exception as e:
                error_msg = f"Error: {str(e)}\n Please fix your mistakes."
                tool_messages.append(
                    ToolMessage(
                        content=error_msg,
                        name=tool_name,
                        tool_call_id=tool_call_id,
                        status="error"
                    )
                )
        
        return State(messages=messages + tool_messages)
    
    return async_tool_node


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
        checkpointer: Optional[BaseCheckpointSaver] = None,
        use_async_tools: bool = True
    ):
        self.tools = tools
        # Check if any tools are async-only (like MCP tools)
        # MCP tools typically only have ainvoke and raise NotImplementedError on invoke
        # We check if tool has ainvoke but doesn't have a working invoke method
        has_async_tools = False
        for tool in tools:
            # If tool has ainvoke, it's likely async
            if hasattr(tool, 'ainvoke'):
                has_async_tools = True
                break
            # If tool has _arun but not _run, it's async-only
            if hasattr(tool, '_arun') and not hasattr(tool, '_run'):
                has_async_tools = True
                break
        
        if use_async_tools and has_async_tools:
            # Use custom async tool node for async tools
            self.tool_node = create_async_tool_node(tools)
        else:
            # Use standard ToolNode for sync tools
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
    
    async def call_model(self, state: State) -> State:
        """
        Call the language model with the current messages.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with model response
        """
        messages = state["messages"]
        
        # Use messages as-is - system message should already be in the conversation
        # from the base class's arun method for new threads
        # Get response from LLM (use ainvoke for async)
        response = await self.llm.ainvoke(messages)
        
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
    
    async def process_message(self, state: State) -> State:
        """
        This method is required by the base class but not used in this implementation.
        The tool agent uses call_model instead.
        """
        return await self.call_model(state)
    
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
    response = asyncio.run(agent.arun("What is 25 * 4 + 10?", config))
    #response = await agent.run("What is 25 * 4 + 10?", config)

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