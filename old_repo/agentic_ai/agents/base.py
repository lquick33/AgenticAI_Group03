"""
Base agent class for all agentic AI agents.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.graph import MessagesState


class State(MessagesState):
    """
    Base state for all agents.
    
    This extends MessagesState to include additional fields while maintaining
    proper message handling with the add_messages reducer.
    """
    store: Optional[Any] # Add store to State for potential access in nodes

class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    This provides a consistent interface for creating different types of agents
    that can be used with LangGraph.
    """
    
    def __init__(
        self, 
        llm: BaseChatModel, 
        name: str = "Agent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None, # Add checkpointer
        store: Optional[BaseStore] = None # Add store
    ):
        self.llm = llm
        self.name = name
        self.system_prompt = system_prompt or f"You are {name}, a helpful AI assistant."
        self.graph = None
        self.checkpointer = checkpointer # Initialize checkpointer
        self.store = store # Initialize store
        self._build_graph()
    
    @abstractmethod
    def _build_graph(self) -> None:
        """Build the LangGraph graph for this agent."""
        pass

    def compile_graph(self, workflow):
        """
        Compile the LangGraph workflow with the configured checkpointer and store.
        """
        if self.checkpointer and self.store:
            self.graph = workflow.compile(checkpointer=self.checkpointer, store=self.store)
        elif self.checkpointer:
            self.graph = workflow.compile(checkpointer=self.checkpointer)
        elif self.store:
            self.graph = workflow.compile(store=self.store)
        else:
            self.graph = workflow.compile()
    
    def run(self, message: str, thread_id: str = "default", user_id: Optional[str] = None, **kwargs) -> str:
        """
        Run the agent with a message.
        
        Args:
            message: User message to process
            thread_id: Unique identifier for the conversation thread.
            user_id: Optional unique identifier for the user (for long-term memory).
            **kwargs: Additional arguments
            
        Returns:
            Agent's response
        """
        if not self.graph:
            raise RuntimeError("Graph not built. Call _build_graph() and compile_graph() first.")
        
        # Configure for persistence
        config = {"configurable": {"thread_id": thread_id}}
        if user_id:
            config["configurable"]["user_id"] = user_id
        
        # Check if this is a new thread or existing thread
        snapshot = self.graph.get_state(config)
        is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")
        
        # Prepare initial messages
        # For new threads, ensure system message is first
        # For existing threads, just add the new HumanMessage (system message already exists)
        if is_new_thread:
            # New thread: prepend system message if available
            messages = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.append(HumanMessage(content=message))
            initial_state = {"messages": messages}
        else:
            # Existing thread: just add the new HumanMessage
            initial_state = {"messages": [HumanMessage(content=message)]}
            
        # Run the graph
        result = self.graph.invoke(initial_state, config)

        return result

    async def arun(self, message: str, thread_id: str = "default", user_id: Optional[str] = None, **kwargs) -> str:
        """
        Run the agent with a message.
        
        Args:
            message: User message to process
            thread_id: Unique identifier for the conversation thread.
            user_id: Optional unique identifier for the user (for long-term memory).
            **kwargs: Additional arguments
            
        Returns:
            Agent's response
        """
        if not self.graph:
            raise RuntimeError("Graph not built. Call _build_graph() and compile_graph() first.")
        
        # Configure for persistence
        config = {"configurable": {"thread_id": thread_id}}
        if user_id:
            config["configurable"]["user_id"] = user_id
        
        # Check if this is a new thread or existing thread
        snapshot = self.graph.get_state(config)
        is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")
        
        # Prepare initial messages
        # For new threads, ensure system message is first
        # For existing threads, just add the new HumanMessage (system message already exists)
        if is_new_thread:
            # New thread: prepend system message if available
            messages = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.append(HumanMessage(content=message))
            initial_state = {"messages": messages}
        else:
            # Existing thread: just add the new HumanMessage
            initial_state = {"messages": [HumanMessage(content=message)]}
            
        # Run the graph
        result = await self.graph.ainvoke(initial_state, config)

        return result
    
    def stream(self, message: str, thread_id: str = "default", user_id: Optional[str] = None, **kwargs):
        """
        Stream the agent's response.
        
        Args:
            message: User message to process
            thread_id: Unique identifier for the conversation thread.
            user_id: Optional unique identifier for the user (for long-term memory).
            **kwargs: Additional arguments
            
        Yields:
            Chunks of the agent's response
        """
        if not self.graph:
            raise RuntimeError("Graph not built. Call _build_graph() and compile_graph() first.")
        
        # Configure for persistence
        config = {"configurable": {"thread_id": thread_id}}
        if user_id:
            config["configurable"]["user_id"] = user_id
        
        # Check if this is a new thread or existing thread
        snapshot = self.graph.get_state(config)
        is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")
        
        # Prepare initial messages
        # For new threads, ensure system message is first
        # For existing threads, just add the new HumanMessage (system message already exists)
        if is_new_thread:
            # New thread: prepend system message if available
            messages = []
            if self.system_prompt:
                messages.append(SystemMessage(content=self.system_prompt))
            messages.append(HumanMessage(content=message))
            initial_state = {"messages": messages}
        else:
            # Existing thread: just add the new HumanMessage
            initial_state = {"messages": [HumanMessage(content=message)]}

        # Stream the graph execution
        for chunk in self.graph.stream(initial_state, config):
            yield chunk
    
    def save_memory(self, user_id: str, key: str, value: dict, namespace: Optional[List[str]] = None):
        """
        Save a long-term memory for a user.
        
        Args:
            user_id: The ID of the user.
            key: A unique key for the memory within the namespace.
            value: The dictionary containing the memory content.
            namespace: Optional list of strings to define a custom namespace.
                       Defaults to [user_id, "memories"].
        """
        if not self.store:
            raise RuntimeError("Memory store not initialized.")
        
        actual_namespace = namespace or [user_id, "memories"]
        self.store.put(tuple(actual_namespace), key, value)

    def retrieve_memory(self, user_id: str, query: Optional[str] = None, namespace: Optional[List[str]] = None, limit: int = 1) -> List[dict]:
        """
        Retrieve long-term memories for a user, optionally using semantic search.
        
        Args:
            user_id: The ID of the user.
            query: Optional natural language query for semantic search.
            namespace: Optional list of strings to define a custom namespace.
                       Defaults to [user_id, "memories"].
            limit: The maximum number of memories to retrieve.
            
        Returns:
            A list of dictionaries containing retrieved memories.
        """
        if not self.store:
            raise RuntimeError("Memory store not initialized.")
            
        actual_namespace = namespace or [user_id, "memories"]
        if query:
            items = self.store.search(tuple(actual_namespace), query=query, limit=limit)
        else:
            items = self.store.search(tuple(actual_namespace), limit=limit)
            
        return [item.value for item in items]

    def get_conversation_history(self, thread_id: str = "default"):
        """
        Get the full conversation history for a thread.
        
        Args:
            thread_id: The thread identifier
            
        Returns:
            List of messages in the conversation
        """
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self.graph.get_state(config)
        if snapshot and snapshot.values:
            return snapshot.values.get("messages", [])
        return []
    
    def add_system_message(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Add system message to the beginning if it doesn't exist.
        
        According to LangGraph best practices, system messages should be:
        1. Added at the beginning of the conversation
        2. Only added once per conversation thread
        3. Preserved across the conversation history
        """
        
        # Check if messages is empty
        if not messages:
            return messages
        
        # Check if there's already a SystemMessage
        has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
        
        if not has_system_message:
            # Ensure system prompt is not None or empty
            if self.system_prompt:
                return [SystemMessage(content=self.system_prompt.format())] + messages
        return messages
    
    def __str__(self) -> str:
        return f"{self.name} (LangGraph Agent)"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', llm={self.llm.__class__.__name__})"
