# Agent Development Rules - Regelwerk für KI-Agenten

Dieses Dokument definiert die Regeln, Patterns und Best Practices für die Entwicklung von KI-Agenten im Lernkompanien-Projekt, basierend auf den Vorgaben aus dem Agentic AI Kurs.

## Inhaltsverzeichnis

1. [Architektur-Übersicht](#architektur-übersicht)
2. [Agent-Entwicklung](#agent-entwicklung)
3. [State Management](#state-management)
4. [Tool-Entwicklung](#tool-entwicklung)
5. [Memory & Persistence](#memory--persistence)
6. [Async & Streaming](#async--streaming)
7. [Best Practices](#best-practices)
8. [Code-Beispiele](#code-beispiele)

---

## Architektur-Übersicht

### BaseAgent Pattern

Alle Agenten müssen von der `BaseAgent` Klasse erben, die folgende Struktur bereitstellt:

**Kern-Komponenten:**
- `_build_graph()`: Abstrakte Methode zum Erstellen des LangGraph-Graphen
- `compile_graph()`: Kompiliert den Graphen mit Checkpointer und Store
- `run()`: Synchrone Ausführung
- `arun()`: Asynchrone Ausführung
- `stream()`: Streaming-Ausführung
- `checkpointer`: Optional für Persistenz
- `store`: Optional für langfristige Erinnerungen

**Wichtig:**
- Jeder Agent muss `_build_graph()` implementieren
- Der Graph wird automatisch mit Checkpointer/Store kompiliert
- System Messages werden automatisch bei neuen Threads hinzugefügt

### State Schema Definition

**Basis-Pattern:**
```python
from langgraph.graph import MessagesState
from typing import TypedDict, Optional, Any

class State(MessagesState):
    """
    Base state for all agents.
    
    This extends MessagesState to include additional fields while maintaining
    proper message handling with the add_messages reducer.
    """
    store: Optional[Any]  # Optional store for memory access
```

**Regeln:**
- IMMER `MessagesState` als Basis verwenden (nicht plain `TypedDict`)
- Zusätzliche Felder können hinzugefügt werden
- `MessagesState` verwendet automatisch `add_messages` Reducer für Message-Handling
- State muss TypedDict sein (für Type Safety)

### Graph Building Pattern

**Standard-Struktur:**
```python
from langgraph.graph import StateGraph, START, END

def _build_graph(self) -> None:
    workflow = StateGraph(state_schema=State)
    
    # Nodes hinzufügen
    workflow.add_node("node_name", self.node_function)
    
    # Edges definieren
    workflow.add_edge(START, "first_node")
    workflow.add_edge("last_node", END)
    
    # Conditional Edges (wenn nötig)
    workflow.add_conditional_edges(
        "decision_node",
        self.should_continue,
        {
            "continue": "next_node",
            "end": END
        }
    )
    
    # Graph kompilieren
    self.compile_graph(workflow)
```

**Regeln:**
- IMMER `StateGraph` mit `state_schema=State` verwenden
- Nodes müssen Funktionen sein, die State akzeptieren und State zurückgeben
- `compile_graph()` wird automatisch aufgerufen (aus BaseAgent)

---

## Agent-Entwicklung

### Erstellen neuer Agenten

**Schritt 1: Von BaseAgent erben**
```python
from agentic_ai.agents.base import BaseAgent, State

class MyAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "MyAgent",
        system_prompt: Optional[str] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        store: Optional[BaseStore] = None
    ):
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            store=store
        )
```

**Schritt 2: Graph definieren**
```python
def _build_graph(self) -> None:
    workflow = StateGraph(state_schema=State)
    
    workflow.add_node("process", self.process_node)
    workflow.add_edge(START, "process")
    workflow.add_edge("process", END)
    
    self.compile_graph(workflow)
```

**Schritt 3: Node-Funktionen implementieren**
```python
def process_node(self, state: State) -> State:
    """
    Process the current state and return updated state.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state
    """
    messages = state["messages"]
    
    # Verarbeitung hier
    response = self.llm.invoke(messages)
    
    # State aktualisieren (MessagesState fügt automatisch hinzu)
    return {"messages": [response]}
```

### Graph-Struktur definieren

**Einfacher Linearer Graph:**
```python
workflow.add_edge(START, "node1")
workflow.add_edge("node1", "node2")
workflow.add_edge("node2", END)
```

**Graph mit Conditional Routing:**
```python
workflow.add_conditional_edges(
    "agent",
    self.should_continue,
    {
        "continue": "tools",
        "end": END
    }
)
```

**Graph mit Loop:**
```python
workflow.add_edge("tools", "agent")  # Zurück zum Agenten
```

### Node-Funktionen implementieren

**Regeln für Node-Funktionen:**
1. **Signatur**: `def node_name(self, state: State) -> State`
2. **Async**: Für async Nodes: `async def node_name(self, state: State) -> State`
3. **Return**: IMMER State zurückgeben (auch wenn nur Teil-Update)
4. **Messages**: MessagesState fügt automatisch neue Messages hinzu
5. **Type Hints**: IMMER Type Hints verwenden

**Beispiel:**
```python
def llm_node(self, state: State) -> State:
    """Call LLM with current messages."""
    messages = state["messages"]
    
    # System message sicherstellen (BaseAgent Methode)
    messages_for_llm = self.add_system_message(messages)
    
    # LLM aufrufen
    response = self.llm.invoke(messages_for_llm)
    
    # Nur Response zurückgeben - MessagesState fügt automatisch hinzu
    return {"messages": [response]}
```

### Conditional Edges und Routing

**Routing-Funktion:**
```python
def should_continue(self, state: State) -> str:
    """
    Determine next step based on state.
    
    Returns:
        String key matching one of the routing options
    """
    last_message = state["messages"][-1]
    
    # Entscheidungslogik
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"  # Gehe zu "tools" node
    else:
        return "end"  # Beende Graph
```

**Regeln:**
- Routing-Funktion muss String zurückgeben
- String muss einem Key im Routing-Dictionary entsprechen
- Für komplexe Logik: Separate Funktionen verwenden

---

## State Management

### MessagesState verwenden

**Warum MessagesState?**
- Automatischer `add_messages` Reducer
- Korrekte Message-Handling
- Thread-sichere Message-Verwaltung

**Verwendung:**
```python
from langgraph.graph import MessagesState

class State(MessagesState):
    # Zusätzliche Felder hier
    pass
```

### Custom State Fields hinzufügen

**Pattern:**
```python
from typing import TypedDict, Optional, List

class MyAgentState(MessagesState):
    """Custom state for MyAgent."""
    current_page: int
    user_id: str
    context: Optional[dict] = None
    metadata: List[str] = []
```

**Regeln:**
- Alle Felder müssen Type Hints haben
- Optional-Felder mit `Optional[Type]` oder `Type | None`
- Default-Werte können gesetzt werden
- IMMER von MessagesState erben

### State Reducers verstehen

**MessagesState Reducer:**
- `add_messages`: Fügt neue Messages zur Liste hinzu (nicht ersetzt)
- Automatisch aktiviert bei `return {"messages": [new_message]}`

**Custom Reducer (falls nötig):**
```python
from langgraph.graph import add_messages

def custom_reducer(left: dict, right: dict) -> dict:
    """Custom reducer for specific field."""
    # Custom logic
    return merged_state

class State(MessagesState):
    custom_field: str  # Würde custom_reducer benötigen
```

**Standard:**
- Für Messages: `add_messages` (automatisch)
- Für andere Felder: Letzter Wert überschreibt (Standard-Verhalten)

---

## Tool-Entwicklung

### BaseTool Pattern

**Alle Tools müssen von BaseTool erben:**
```python
from agentic_ai.tools.base import BaseTool
from langchain_core.tools import BaseTool as LangChainBaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Clear description of what the tool does."
        )
    
    def run(self, *args, **kwargs) -> Any:
        """Execute the tool synchronously."""
        # Implementation
        pass
    
    def to_langchain_tool(self) -> LangChainBaseTool:
        """Convert to LangChain tool."""
        # Implementation
        pass
```

**Regeln:**
- `name`: Kurz, eindeutig, snake_case
- `description`: Detailliert (wird vom LLM verwendet)
- `run()`: Synchrone Implementierung
- `to_langchain_tool()`: Konvertierung für LangChain

### LangChain Tool Conversion

**StructuredTool (empfohlen für komplexe Inputs):**
```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    """Input schema for the tool."""
    param1: str = Field(description="Description of param1")
    param2: int = Field(default=10, description="Description of param2")

def to_langchain_tool(self) -> StructuredTool:
    def tool_wrapper(param1: str, param2: int = 10) -> str:
        return self._run(param1=param1, param2=param2)
    
    return StructuredTool(
        name=self.name,
        description=self.description,
        func=tool_wrapper,
        args_schema=MyToolInput
    )
```

**Standard Tool (für einfache Inputs):**
```python
from langchain_core.tools import Tool

def to_langchain_tool(self) -> Tool:
    return Tool(
        name=self.name,
        description=self.description,
        func=self.run
    )
```

### Async Tool Support

**Problem:** Manche Tools (z.B. MCP Tools) sind nur async verfügbar.

**Lösung: Custom Async Tool Node:**
```python
async def create_async_tool_node(tools: List[BaseTool]):
    """Create async tool node that handles both sync and async tools."""
    tool_map = {tool.name: tool for tool in tools}
    
    async def async_tool_node(state: State) -> State:
        messages = state["messages"]
        last_message = messages[-1]
        
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            return state
        
        tool_messages = []
        
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id")
            
            tool = tool_map[tool_name]
            
            # Priority: ainvoke > _arun > invoke (in thread) > _run (in thread)
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(tool_args)
            elif hasattr(tool, '_arun'):
                result = await tool._arun(**tool_args)
            elif hasattr(tool, 'invoke'):
                result = await asyncio.to_thread(tool.invoke, tool_args)
            elif hasattr(tool, '_run'):
                result = await asyncio.to_thread(tool._run, **tool_args)
            else:
                raise ValueError(f"Tool {tool_name} does not have a callable method")
            
            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    name=tool_name,
                    tool_call_id=tool_call_id
                )
            )
        
        return State(messages=messages + tool_messages)
    
    return async_tool_node
```

**Verwendung im Agent:**
```python
# Prüfen ob async Tools vorhanden
has_async_tools = any(
    hasattr(tool, 'ainvoke') or 
    (hasattr(tool, '_arun') and not hasattr(tool, '_run'))
    for tool in tools
)

if use_async_tools and has_async_tools:
    self.tool_node = create_async_tool_node(tools)
else:
    self.tool_node = ToolNode(tools)  # Standard LangGraph ToolNode
```

### Tool Registry Pattern

**Tool Registry für Organisation:**
```python
from agentic_ai.tools.base import ToolRegistry

registry = ToolRegistry()

# Tools registrieren
registry.register(calculator_tool, category="math")
registry.register(url_fetcher_tool, category="web")

# Tools abrufen
math_tools = registry.get_tools_by_category("math")
all_tools = registry.get_all_tools()
langchain_tools = registry.get_langchain_tools(categories=["math", "web"])
```

**Vorteile:**
- Organisierte Tool-Verwaltung
- Kategorisierung
- Einfache Filterung nach Kategorien

---

## Memory & Persistence

### Checkpointing Setup

**Checkpointer initialisieren:**
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

# Für Entwicklung (Memory)
checkpointer = InMemorySaver()

# Für Produktion (PostgreSQL)
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/db"
)
```

**Agent mit Checkpointer:**
```python
agent = MyAgent(
    llm=llm,
    checkpointer=checkpointer
)
```

### Thread Management

**Thread-ID verwenden:**
```python
# Neue Konversation
result = agent.run(
    "Hello",
    thread_id="user_123_conversation_1"
)

# Fortsetzen der Konversation
result = agent.run(
    "What did I say before?",
    thread_id="user_123_conversation_1"  # Gleiche Thread-ID
)
```

**User-ID für langfristige Erinnerungen:**
```python
result = agent.run(
    "Remember my favorite color is blue",
    thread_id="conversation_1",
    user_id="user_123"  # Für langfristige Erinnerungen
)
```

**Regeln:**
- `thread_id`: Eindeutig pro Konversation
- `user_id`: Eindeutig pro Benutzer (optional, für Memory)
- Threads werden automatisch persistiert mit Checkpointer

### Long-term Memory (Store)

**Store initialisieren:**
```python
from langgraph.store.memory import MemoryStore

store = MemoryStore()

agent = MyAgent(
    llm=llm,
    store=store
)
```

**Memory speichern:**
```python
agent.save_memory(
    user_id="user_123",
    key="favorite_color",
    value={"color": "blue", "timestamp": "2024-01-01"},
    namespace=["user_123", "preferences"]  # Optional
)
```

**Memory abrufen:**
```python
# Semantische Suche
memories = agent.retrieve_memory(
    user_id="user_123",
    query="What is my favorite color?",
    limit=5
)

# Alle Memories
all_memories = agent.retrieve_memory(
    user_id="user_123",
    limit=10
)
```

**Namespace-Pattern:**
- Standard: `[user_id, "memories"]`
- Custom: `["user_123", "preferences"]`, `["user_123", "facts"]`
- Ermöglicht organisierte Memory-Struktur

### Conversation History

**History abrufen:**
```python
history = agent.get_conversation_history(thread_id="conversation_1")

for msg in history:
    print(f"{msg.__class__.__name__}: {msg.content}")
```

**Regeln:**
- History enthält alle Messages im Thread
- System Messages sind enthalten
- Tool Messages sind enthalten
- Kann für Context-Retrieval verwendet werden

---

## Async & Streaming

### Async Node Functions

**Pattern:**
```python
async def async_node(self, state: State) -> State:
    """Async node function."""
    messages = state["messages"]
    
    # Async LLM call
    response = await self.llm.ainvoke(messages)
    
    return {"messages": [response]}
```

**Regeln:**
- Node-Funktion muss `async def` sein
- `await` für alle async Operationen
- Graph kann Mix aus sync und async Nodes haben

### Streaming Responses

**Streaming im Agent:**
```python
for chunk in agent.stream(
    "Tell me a story",
    thread_id="conversation_1"
):
    # Chunk verarbeiten
    print(chunk)
```

**Streaming-Format:**
```python
# Chunk-Struktur:
{
    "node_name": {
        "messages": [AIMessage(...)]
    }
}
```

**Frontend-Integration:**
```python
# FastAPI Endpoint
@app.post("/api/chat/stream")
async def stream_chat(request: ChatRequest):
    async def event_generator():
        async for chunk in agent.stream(
            request.message,
            thread_id=request.thread_id,
            user_id=request.user_id
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Regeln:**
- IMMER `async for` für Streaming verwenden
- Server-Sent Events (SSE) für Frontend
- Chunks können von verschiedenen Nodes kommen

### Error Handling in Async Context

**Pattern:**
```python
async def safe_async_node(self, state: State) -> State:
    """Async node with error handling."""
    try:
        messages = state["messages"]
        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}
    except Exception as e:
        # Error Message zurückgeben
        error_msg = AIMessage(
            content=f"Error: {str(e)}",
            additional_kwargs={"error": True}
        )
        return {"messages": [error_msg]}
```

**Regeln:**
- IMMER try/except in async Nodes
- Fehler als Messages zurückgeben (nicht Exceptions werfen)
- Logging für Debugging

---

## Best Practices

### System Message Handling

**Automatisches Handling (BaseAgent):**
- System Message wird bei neuen Threads automatisch hinzugefügt
- Bei bestehenden Threads bleibt System Message erhalten
- `add_system_message()` Methode für Fallback-Checks

**Manuelles Handling (falls nötig):**
```python
def llm_node(self, state: State) -> State:
    messages = state["messages"]
    
    # Sicherstellen dass System Message vorhanden
    messages_for_llm = self.add_system_message(messages)
    
    response = self.llm.invoke(messages_for_llm)
    return {"messages": [response]}
```

**Gemini-spezifisch (mit Tools):**
```python
# Für Gemini mit bound tools: System Message nicht als SystemMessage
# Stattdessen in erste HumanMessage einbetten
if not has_system_message and self.system_prompt:
    modified_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage) and not system_prepended:
            new_content = f"{self.system_prompt}\n\nUser: {msg.content}"
            modified_messages.append(HumanMessage(content=new_content))
            system_prepended = True
        else:
            modified_messages.append(msg)
    messages_to_use = modified_messages
```

### Error Handling

**Node-Level:**
```python
def safe_node(self, state: State) -> State:
    try:
        # Operation
        result = perform_operation()
        return {"result": result}
    except SpecificException as e:
        # Spezifischer Fehler
        logger.error(f"Specific error: {e}")
        return {"error": str(e)}
    except Exception as e:
        # Allgemeiner Fehler
        logger.error(f"Unexpected error: {e}")
        return {"error": "An error occurred"}
```

**Tool-Level:**
```python
def _run(self, param: str) -> str:
    try:
        # Tool logic
        return result
    except Exception as e:
        return f"Error: {str(e)}"  # IMMER String zurückgeben
```

**Regeln:**
- Fehler als Messages/Values zurückgeben (nicht Exceptions)
- Logging für alle Fehler
- Spezifische Exception-Types verwenden

### Logging & Debugging

**Logging-Setup:**
```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

**In Nodes:**
```python
def debug_node(self, state: State) -> State:
    logger.debug(f"State: {state}")
    logger.info(f"Processing {len(state['messages'])} messages")
    
    # Processing
    
    logger.debug(f"Updated state: {state}")
    return state
```

**LangGraph Tracing:**
```python
# Mit LangSmith/LangFuse
from langfuse import Langfuse

langfuse = Langfuse()

# Agent mit Tracing
agent = MyAgent(
    llm=llm,
    # Tracing wird automatisch aktiviert wenn LangFuse konfiguriert ist
)
```

### Testing Patterns

**Unit Test für Agent:**
```python
import pytest
from langgraph.checkpoint.memory import InMemorySaver

@pytest.fixture
def agent():
    llm = init_chat_model("gemini-2.5-flash-lite")
    checkpointer = InMemorySaver()
    return MyAgent(llm=llm, checkpointer=checkpointer)

def test_agent_basic(agent):
    result = agent.run("Hello", thread_id="test")
    assert "messages" in result
    assert len(result["messages"]) > 0

def test_agent_memory(agent):
    agent.run("Remember: I like pizza", thread_id="test", user_id="user1")
    memories = agent.retrieve_memory("user1", query="pizza")
    assert len(memories) > 0
```

**Integration Test:**
```python
def test_agent_tool_integration(agent):
    result = agent.run("Calculate 2+2", thread_id="test")
    # Prüfe ob Tool aufgerufen wurde
    history = agent.get_conversation_history("test")
    tool_messages = [m for m in history if isinstance(m, ToolMessage)]
    assert len(tool_messages) > 0
```

---

## Code-Beispiele

### SimpleAgent Pattern

**Vollständiges Beispiel:**
```python
from langgraph.graph import StateGraph, START, END
from agentic_ai.agents.base import BaseAgent, State
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

class SimpleAgent(BaseAgent):
    """
    A simple conversational agent without tools.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        name: str = "SimpleAgent",
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None
    ):
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer
        )
    
    def _build_graph(self) -> None:
        workflow = StateGraph(state_schema=State)
        
        workflow.add_node("llm_node", self.llm_node)
        workflow.add_edge(START, "llm_node")
        workflow.add_edge("llm_node", END)
        
        self.compile_graph(workflow)
    
    def llm_node(self, state: State) -> State:
        """Call LLM with current messages."""
        messages = state["messages"]
        messages_for_llm = self.add_system_message(messages)
        response = self.llm.invoke(messages_for_llm)
        return {"messages": [response]}
```

### ToolAgent Pattern

**Vollständiges Beispiel:**
```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from agentic_ai.agents.base import BaseAgent, State
from langchain_core.tools import BaseTool

class ToolAgent(BaseAgent):
    """
    Agent that can use tools.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        name: str = "ToolAgent",
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None
    ):
        self.tools = tools
        self.tool_node = ToolNode(tools)
        
        super().__init__(
            llm=llm.bind_tools(tools),  # Tools an LLM binden
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer
        )
    
    def _build_graph(self) -> None:
        workflow = StateGraph(State)
        
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        
        workflow.add_edge("tools", "agent")
        
        self.compile_graph(workflow)
    
    def call_model(self, state: State) -> State:
        """Call LLM with current messages."""
        messages = state["messages"]
        response = self.llm.invoke(messages)
        return State(
            messages=messages + [response],
            next_step=None
        )
    
    def should_continue(self, state: State) -> str:
        """Determine if tools should be called."""
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        return "end"
```

### Async ToolAgent Pattern

**Vollständiges Beispiel:**
```python
import asyncio
from langchain_core.messages import ToolMessage

class AsyncToolAgent(BaseAgent):
    """
    Agent with async tool support.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        use_async_tools: bool = True,
        **kwargs
    ):
        self.tools = tools
        
        # Prüfe ob async Tools vorhanden
        has_async_tools = any(
            hasattr(tool, 'ainvoke') or 
            (hasattr(tool, '_arun') and not hasattr(tool, '_run'))
            for tool in tools
        )
        
        if use_async_tools and has_async_tools:
            self.tool_node = create_async_tool_node(tools)
        else:
            from langgraph.prebuilt import ToolNode
            self.tool_node = ToolNode(tools)
        
        super().__init__(
            llm=llm.bind_tools(tools),
            **kwargs
        )
    
    def _build_graph(self) -> None:
        workflow = StateGraph(State)
        
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {"continue": "tools", "end": END}
        )
        
        workflow.add_edge("tools", "agent")
        
        self.compile_graph(workflow)
    
    async def call_model(self, state: State) -> State:
        """Async call to LLM."""
        messages = state["messages"]
        response = await self.llm.ainvoke(messages)
        return State(messages=messages + [response])
    
    def should_continue(self, state: State) -> str:
        """Determine if tools should be called."""
        last_message = state["messages"][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        return "end"
```

### Dynamic Prompt Agent

**Vollständiges Beispiel:**
```python
from datetime import datetime
from langchain.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

class DynamicPromptAgent(BaseAgent):
    """
    Agent with dynamic system prompts.
    """
    
    def __init__(self, llm, name, system_prompt=None, checkpointer=None):
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=self.init_prompt(system_prompt),
            checkpointer=checkpointer
        )
    
    def _build_graph(self) -> None:
        workflow = StateGraph(state_schema=State)
        
        workflow.add_node("update_system_prompt", self.update_system_prompt)
        workflow.add_node("llm_node", self.llm_node)
        
        workflow.add_edge(START, "update_system_prompt")
        workflow.add_edge("update_system_prompt", "llm_node")
        workflow.add_edge("llm_node", END)
        
        self.compile_graph(workflow)
    
    def update_system_prompt(self, state: State) -> Command:
        """Update system prompt dynamically."""
        current_messages = state["messages"]
        formatted_system_prompt = self.system_prompt.format()
        current_messages[0].content = formatted_system_prompt
        return Command(update={"messages": current_messages})
    
    def llm_node(self, state: State) -> State:
        """Call LLM with updated messages."""
        current_messages = state["messages"]
        response = self.llm.invoke(current_messages)
        return {"messages": [response]}
    
    def init_prompt(self, prompt: str) -> PromptTemplate:
        """Initialize dynamic prompt template."""
        system_prompt_template = PromptTemplate(
            input_variables=["name", "date"],
            template=prompt
        )
        
        def get_current_time():
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        def get_current_name():
            return self.name
        
        return system_prompt_template.partial(
            date=get_current_time,
            name=get_current_name
        )
```

---

## Zusammenfassung der Regeln

### MUSS-Regeln (Mandatory)

1. ✅ **Alle Agenten müssen von BaseAgent erben**
2. ✅ **State muss MessagesState erweitern**
3. ✅ **Graph muss mit StateGraph erstellt werden**
4. ✅ **Nodes müssen State akzeptieren und State zurückgeben**
5. ✅ **Type Hints sind Pflicht**
6. ✅ **Tools müssen BaseTool erben**
7. ✅ **Checkpointer für Persistenz verwenden**
8. ✅ **Thread-ID für Konversations-Management**

### SOLLTE-Regeln (Best Practices)

1. 💡 **Async für I/O-Operationen verwenden**
2. 💡 **Streaming für lange Antworten**
3. 💡 **Error Handling in allen Nodes**
4. 💡 **Logging für Debugging**
5. 💡 **Tool Registry für Organisation**
6. 💡 **Memory Store für langfristige Erinnerungen**
7. 💡 **Unit Tests für Agenten schreiben**

### NICHT-Regeln (Anti-Patterns)

1. ❌ **NICHT plain dict für State verwenden**
2. ❌ **NICHT Exceptions in Nodes werfen (als Messages zurückgeben)**
3. ❌ **NICHT System Messages manuell bei jedem Call hinzufügen**
4. ❌ **NICHT sync Tools in async Context blockieren**
5. ❌ **NICHT ohne Type Hints entwickeln**

---

## Referenzen

- **Kurs-Repository**: `old_repo/agentic_ai/`
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **LangChain Docs**: https://python.langchain.com/
- **Projekt-Plan**: `PROJECT_PLAN.md`
- **Cursor Rules**: `.cursorrules`

---

**Letzte Aktualisierung**: 2024-01-XX
**Version**: 1.0
**Autor**: Basierend auf Agentic AI Kurs-Vorgaben
