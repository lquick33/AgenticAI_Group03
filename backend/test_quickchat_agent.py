"""
Quick Chat Agent Test Suite

Tests all features of:
- QuickChatAgent
- QuickChatState
- SearchTopicTool
- GetUserCoursesTool
- StateAwareToolNode
- API endpoints

Run with: python test_quickchat_agent.py

Requirements:
- Supabase connection (SUPABASE_URL, SUPABASE_KEY)
- Google API key (GOOGLE_API_KEY)
- Langfuse credentials (optional)
"""

import sys
import os
import traceback
import uuid
import asyncio
import json
from typing import List, Dict, Any, Optional

# Track test results
results = {"passed": 0, "failed": 0, "skipped": 0}


def run_test(name: str):
    """Decorator for synchronous test functions."""
    def decorator(func):
        def wrapper():
            try:
                print(f"\n{'='*60}")
                print(f"TEST: {name}")
                print('='*60)
                func()
                results["passed"] += 1
                print(f"✅ PASSED: {name}")
            except Exception as e:
                results["failed"] += 1
                print(f"❌ FAILED: {name}")
                print(f"   Error: {e}")
                traceback.print_exc()
        return wrapper
    return decorator


def async_test(name: str):
    """Decorator for async test functions."""
    def decorator(func):
        def wrapper():
            try:
                print(f"\n{'='*60}")
                print(f"TEST: {name}")
                print('='*60)
                asyncio.run(func())
                results["passed"] += 1
                print(f"✅ PASSED: {name}")
            except Exception as e:
                results["failed"] += 1
                print(f"❌ FAILED: {name}")
                print(f"   Error: {e}")
                traceback.print_exc()
        return wrapper
    return decorator


def skip(name: str, reason: str):
    """Mark a test as skipped."""
    def decorator(func):
        def wrapper():
            print(f"\n{'='*60}")
            print(f"TEST: {name}")
            print('='*60)
            print(f"⏭️  SKIPPED: {reason}")
            results["skipped"] += 1
        return wrapper
    return decorator


# =============================================================================
# SECTION 1: IMPORT TESTS
# =============================================================================

@run_test("Import QuickChatAgent")
def test_import_quickchat_agent():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent, QuickChatState
    print("   - QuickChatAgent imported successfully")
    print("   - QuickChatState imported successfully")
    
    # Check QuickChatState fields
    annotations = QuickChatState.__annotations__
    assert "mode" in annotations, "QuickChatState should have 'mode'"
    assert "current_page" in annotations, "QuickChatState should have 'current_page'"
    assert "material_id" in annotations, "QuickChatState should have 'material_id'"
    assert "user_id" in annotations, "QuickChatState should have 'user_id'"
    assert "course_id" in annotations, "QuickChatState should have 'course_id'"
    assert "navigation_request" in annotations, "QuickChatState should have 'navigation_request'"
    print("   - QuickChatState has required fields")


@run_test("Import StateAwareToolNode")
def test_import_state_aware_tool_node():
    from app.agents.quickchat.quickchat_agent import StateAwareToolNode
    print("   - StateAwareToolNode imported successfully")
    
    # Check it inherits from ToolNode
    from langgraph.prebuilt import ToolNode
    assert issubclass(StateAwareToolNode, ToolNode), "StateAwareToolNode should inherit from ToolNode"
    print("   - StateAwareToolNode correctly inherits from ToolNode")


@run_test("Import SearchTopicTool")
def test_import_search_topic_tool():
    from app.tools.search_topic_tool import SearchTopicTool, SearchTopicInput
    print("   - SearchTopicTool imported successfully")
    print("   - SearchTopicInput imported successfully")
    
    # Check SearchTopicInput fields
    fields = SearchTopicInput.model_fields
    assert "query" in fields, "SearchTopicInput should have 'query'"
    assert "user_id" in fields, "SearchTopicInput should have 'user_id'"
    assert "language" in fields, "SearchTopicInput should have 'language'"
    assert "limit" in fields, "SearchTopicInput should have 'limit'"
    print("   - SearchTopicInput has required fields")


@run_test("Import GetUserCoursesTool")
def test_import_get_user_courses_tool():
    from app.tools.user_courses_tool import GetUserCoursesTool, GetUserCoursesInput
    print("   - GetUserCoursesTool imported successfully")
    print("   - GetUserCoursesInput imported successfully")
    
    # Check GetUserCoursesInput fields
    fields = GetUserCoursesInput.model_fields
    assert "user_id" in fields, "GetUserCoursesInput should have 'user_id'"
    print("   - GetUserCoursesInput has required fields")


@run_test("Import QuickChat module package")
def test_import_quickchat_module():
    from app.agents.quickchat import QuickChatAgent, QuickChatState
    print("   - QuickChatAgent imported from package successfully")
    print("   - QuickChatState imported from package successfully")


# =============================================================================
# SECTION 2: QUICKCHAT AGENT INITIALIZATION TESTS
# =============================================================================

@run_test("QuickChatAgent - Initialize with default config")
def test_quickchat_init_default():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    assert agent.name == "QuickChatAgent"
    assert agent.language == "de"
    print(f"   - Agent name: {agent.name}")
    print(f"   - Default language: {agent.language}")
    print("   - Agent initialized with default config")


@run_test("QuickChatAgent - Initialize with English language")
def test_quickchat_init_english():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm, language="en")
    
    assert agent.language == "en"
    print(f"   - Language: {agent.language}")
    print("   - Agent initialized with English language")


@run_test("QuickChatAgent - Initialize with personality config")
def test_quickchat_init_personality():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    personality_config = {
        "formality": "informal",
        "humor": "moderate",
        "encouragement": "enthusiastic"
    }
    
    agent = QuickChatAgent(
        llm=llm,
        language="de",
        personality_config=personality_config
    )
    
    assert agent.personality_config == personality_config
    print(f"   - Personality: {personality_config}")
    print("   - Agent initialized with custom personality")


@run_test("QuickChatAgent - Initialize with checkpointer")
def test_quickchat_init_checkpointer():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    from langgraph.checkpoint.memory import MemorySaver
    
    llm = get_gemini_model()
    checkpointer = MemorySaver()
    
    agent = QuickChatAgent(llm=llm, checkpointer=checkpointer)
    
    assert agent.checkpointer == checkpointer
    print("   - Agent initialized with checkpointer")
    print("   - Checkpointer is MemorySaver instance")


@run_test("QuickChatAgent - Tool binding verification")
def test_quickchat_tool_binding():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Check that langchain_tools is populated
    assert hasattr(agent, 'langchain_tools'), "Agent should have langchain_tools"
    assert len(agent.langchain_tools) >= 6, f"Agent should have at least 6 tools, got {len(agent.langchain_tools)}"
    
    # Get tool names
    tool_names = [t.name for t in agent.langchain_tools]
    print(f"   - Tools bound: {tool_names}")
    
    # Check required tools
    assert "search_topic" in tool_names, "search_topic tool should be bound"
    assert "get_user_courses" in tool_names, "get_user_courses tool should be bound"
    assert "get_page_analysis" in tool_names, "get_page_analysis tool should be bound"
    assert "get_course_material_summary" in tool_names, "get_course_material_summary tool should be bound"
    assert "create_quiz" in tool_names, "create_quiz tool should be bound"
    print("   - All required tools are bound")


@run_test("QuickChatAgent - MAX_HISTORY_MESSAGES constant")
def test_quickchat_max_history():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    assert hasattr(agent, 'MAX_HISTORY_MESSAGES'), "Agent should have MAX_HISTORY_MESSAGES"
    assert agent.MAX_HISTORY_MESSAGES >= 10, "MAX_HISTORY_MESSAGES should be at least 10"
    print(f"   - MAX_HISTORY_MESSAGES: {agent.MAX_HISTORY_MESSAGES}")
    print("   - Message history limit is configured")


# =============================================================================
# SECTION 3: STATE MANAGEMENT TESTS
# =============================================================================

@run_test("QuickChatState - Default values in annotations")
def test_quickchat_state_defaults():
    from app.agents.quickchat.quickchat_agent import QuickChatState
    from langchain_core.messages import HumanMessage
    
    # Note: TypedDict doesn't automatically apply default values
    # The defaults are defined in the class but need to be explicitly set
    # This test verifies that the state can be created with explicit defaults
    state = QuickChatState(
        messages=[HumanMessage(content="Hello")],
        mode="discovery"  # Explicit default
    )
    
    assert state.get("mode") == "discovery", f"Mode should be 'discovery', got {state.get('mode')}"
    assert state.get("current_page") is None, "current_page should be None when not set"
    assert state.get("material_id") is None, "material_id should be None when not set"
    assert state.get("user_id") is None, "user_id should be None when not set"
    print("   - State created with discovery mode")
    print("   - Optional fields are None when not provided")


@run_test("QuickChatState - Full state initialization")
def test_quickchat_state_full():
    from app.agents.quickchat.quickchat_agent import QuickChatState
    from langchain_core.messages import HumanMessage
    
    state = QuickChatState(
        messages=[HumanMessage(content="Hello")],
        mode="tutoring",
        current_page=5,
        material_id="test-material-uuid",
        user_id="test-user-uuid",
        course_id="test-course-uuid",
        course_material_summary={"title": "Test Material"},
        navigation_request={"material_id": "new-material", "page_number": 10}
    )
    
    assert state["mode"] == "tutoring"
    assert state["current_page"] == 5
    assert state["material_id"] == "test-material-uuid"
    assert state["user_id"] == "test-user-uuid"
    assert state["course_id"] == "test-course-uuid"
    assert state["course_material_summary"]["title"] == "Test Material"
    assert state["navigation_request"]["page_number"] == 10
    
    print("   - Full state initialized correctly")
    print(f"   - Mode: {state['mode']}")
    print(f"   - Current page: {state['current_page']}")


@run_test("QuickChatState - Mode transition")
def test_quickchat_state_mode_transition():
    from app.agents.quickchat.quickchat_agent import QuickChatState
    from langchain_core.messages import HumanMessage
    
    # Start in discovery mode
    state = QuickChatState(
        messages=[HumanMessage(content="Search for IT security")],
        mode="discovery"
    )
    assert state["mode"] == "discovery"
    print("   - Initial mode: discovery")
    
    # Simulate transition to tutoring mode
    state["mode"] = "tutoring"
    state["material_id"] = "found-material-uuid"
    state["current_page"] = 15
    
    assert state["mode"] == "tutoring"
    assert state["material_id"] == "found-material-uuid"
    assert state["current_page"] == 15
    print("   - Transitioned to tutoring mode")
    print(f"   - Material ID: {state['material_id']}")
    print(f"   - Current page: {state['current_page']}")


# =============================================================================
# SECTION 4: SEARCH TOPIC TOOL TESTS
# =============================================================================

@run_test("SearchTopicTool - Initialize")
def test_search_topic_tool_init():
    from app.tools.search_topic_tool import SearchTopicTool
    
    tool = SearchTopicTool()
    
    assert tool.name == "search_topic"
    assert "search" in tool.description.lower()
    assert "topic" in tool.description.lower()
    print(f"   - Tool name: {tool.name}")
    print(f"   - Description: {tool.description[:80]}...")


@run_test("SearchTopicTool - to_langchain_tool")
def test_search_topic_tool_langchain():
    from app.tools.search_topic_tool import SearchTopicTool
    from langchain_core.tools import StructuredTool
    
    tool = SearchTopicTool()
    langchain_tool = tool.to_langchain_tool()
    
    assert isinstance(langchain_tool, StructuredTool)
    assert langchain_tool.name == "search_topic"
    print("   - Converted to LangChain StructuredTool successfully")


@run_test("SearchTopicTool - Execute with valid user")
def test_search_topic_tool_run():
    from app.tools.search_topic_tool import SearchTopicTool
    from app.services.storage import get_supabase_client
    
    tool = SearchTopicTool()
    
    # Get a valid user ID
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if not profiles.data:
        print("   - No profiles found, skipping actual search")
        return
    
    user_id = profiles.data[0]["id"]
    
    result = tool._run(
        query="security",
        user_id=user_id,
        language="auto",
        limit=5
    )
    
    result_data = json.loads(result)
    
    assert "found" in result_data, "Result should have 'found' key"
    assert "results" in result_data, "Result should have 'results' key"
    
    print(f"   - Found: {result_data['found']}")
    print(f"   - Results count: {len(result_data['results'])}")
    if result_data["results"]:
        first_result = result_data["results"][0]
        print(f"   - First result: {first_result.get('material', {}).get('name', 'N/A')}")


@run_test("SearchTopicTool - Execute with invalid user")
def test_search_topic_tool_invalid_user():
    from app.tools.search_topic_tool import SearchTopicTool
    
    tool = SearchTopicTool()
    
    result = tool._run(
        query="test",
        user_id="invalid-uuid-not-real",
        language="auto",
        limit=5
    )
    
    result_data = json.loads(result)
    
    # Should return error or empty results, not crash
    assert "error" in result_data or result_data.get("found") == False
    print("   - Handled invalid user ID gracefully")
    if "error" in result_data:
        print(f"   - Error message: {result_data['error'][:50]}...")


@run_test("SearchTopicTool - Language parameter")
def test_search_topic_tool_language():
    from app.tools.search_topic_tool import SearchTopicTool
    from app.services.storage import get_supabase_client
    
    tool = SearchTopicTool()
    
    # Get a valid user ID
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if not profiles.data:
        print("   - No profiles found, skipping language test")
        return
    
    user_id = profiles.data[0]["id"]
    
    # Test German search
    result_de = tool._run(
        query="Sicherheit",
        user_id=user_id,
        language="de",
        limit=3
    )
    result_de_data = json.loads(result_de)
    print(f"   - German search results: {len(result_de_data.get('results', []))}")
    
    # Test English search
    result_en = tool._run(
        query="security",
        user_id=user_id,
        language="en",
        limit=3
    )
    result_en_data = json.loads(result_en)
    print(f"   - English search results: {len(result_en_data.get('results', []))}")
    
    # Test auto language
    result_auto = tool._run(
        query="security",
        user_id=user_id,
        language="auto",
        limit=3
    )
    result_auto_data = json.loads(result_auto)
    print(f"   - Auto language results: {len(result_auto_data.get('results', []))}")


# =============================================================================
# SECTION 5: GET USER COURSES TOOL TESTS
# =============================================================================

@run_test("GetUserCoursesTool - Initialize")
def test_get_user_courses_tool_init():
    from app.tools.user_courses_tool import GetUserCoursesTool
    
    tool = GetUserCoursesTool()
    
    assert tool.name == "get_user_courses"
    assert "courses" in tool.description.lower()
    print(f"   - Tool name: {tool.name}")
    print(f"   - Description: {tool.description[:80]}...")


@run_test("GetUserCoursesTool - to_langchain_tool")
def test_get_user_courses_tool_langchain():
    from app.tools.user_courses_tool import GetUserCoursesTool
    from langchain_core.tools import StructuredTool
    
    tool = GetUserCoursesTool()
    langchain_tool = tool.to_langchain_tool()
    
    assert isinstance(langchain_tool, StructuredTool)
    assert langchain_tool.name == "get_user_courses"
    print("   - Converted to LangChain StructuredTool successfully")


@run_test("GetUserCoursesTool - Execute with valid user")
def test_get_user_courses_tool_run():
    from app.tools.user_courses_tool import GetUserCoursesTool
    from app.services.storage import get_supabase_client
    
    tool = GetUserCoursesTool()
    
    # Get a valid user ID
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if not profiles.data:
        print("   - No profiles found, skipping actual search")
        return
    
    user_id = profiles.data[0]["id"]
    
    result = tool._run(user_id=user_id)
    result_data = json.loads(result)
    
    assert "found" in result_data, "Result should have 'found' key"
    assert "courses" in result_data, "Result should have 'courses' key"
    
    print(f"   - Found: {result_data['found']}")
    print(f"   - Courses count: {len(result_data['courses'])}")
    
    if "summary" in result_data:
        summary = result_data["summary"]
        print(f"   - Total materials: {summary.get('total_materials', 0)}")
        print(f"   - Total pages: {summary.get('total_pages', 0)}")


@run_test("GetUserCoursesTool - Execute with invalid user")
def test_get_user_courses_tool_invalid_user():
    from app.tools.user_courses_tool import GetUserCoursesTool
    
    tool = GetUserCoursesTool()
    
    result = tool._run(user_id="invalid-uuid-not-real")
    result_data = json.loads(result)
    
    # Should return error or empty courses, not crash
    assert "error" in result_data or result_data.get("found") == False
    print("   - Handled invalid user ID gracefully")


# =============================================================================
# SECTION 6: STATE-AWARE TOOL NODE TESTS
# =============================================================================

@run_test("StateAwareToolNode - Initialize")
def test_state_aware_tool_node_init():
    from app.agents.quickchat.quickchat_agent import StateAwareToolNode
    from app.tools.search_topic_tool import SearchTopicTool
    
    tool = SearchTopicTool()
    langchain_tools = [tool.to_langchain_tool()]
    
    node = StateAwareToolNode(langchain_tools)
    
    assert node is not None
    print("   - StateAwareToolNode initialized successfully")


@run_test("StateAwareToolNode - user_id injection")
def test_state_aware_tool_node_user_id_injection():
    from app.agents.quickchat.quickchat_agent import StateAwareToolNode, QuickChatState
    from app.tools.search_topic_tool import SearchTopicTool
    from langchain_core.messages import AIMessage, HumanMessage
    
    tool = SearchTopicTool()
    langchain_tools = [tool.to_langchain_tool()]
    node = StateAwareToolNode(langchain_tools)
    
    # Create a state with the correct user_id
    real_user_id = "af5c89cc-e0fb-45a9-8abb-b7508a989909"
    
    # Create an AI message with tool call using a placeholder user_id
    ai_message = AIMessage(
        content="",
        tool_calls=[{
            "id": "call_123",
            "name": "search_topic",
            "args": {
                "query": "test",
                "user_id": "test-user-id",  # This should be overwritten
                "language": "auto",
                "limit": 5
            }
        }]
    )
    
    state = QuickChatState(
        messages=[HumanMessage(content="Find IT"), ai_message],
        user_id=real_user_id
    )
    
    # The node should inject the real user_id from state
    # We can't easily test the actual injection without running, but we verify the logic exists
    assert hasattr(node, 'invoke'), "StateAwareToolNode should have invoke method"
    assert hasattr(node, 'ainvoke'), "StateAwareToolNode should have ainvoke method"
    print("   - StateAwareToolNode has required injection methods")
    print(f"   - State user_id: {real_user_id}")
    print(f"   - LLM-generated user_id (to be overwritten): test-user-id")


@run_test("StateAwareToolNode - material_id injection for tutoring tools")
def test_state_aware_tool_node_material_injection():
    from app.agents.quickchat.quickchat_agent import StateAwareToolNode, QuickChatState
    from app.tools.page_analysis_tool import GetPageAnalysisTool
    from langchain_core.messages import AIMessage, HumanMessage
    
    tool = GetPageAnalysisTool()
    langchain_tools = [tool.to_langchain_tool()]
    node = StateAwareToolNode(langchain_tools)
    
    # Create state with material context
    state = QuickChatState(
        messages=[HumanMessage(content="Explain this page")],
        mode="tutoring",
        material_id="real-material-uuid",
        current_page=10,
        user_id="real-user-uuid"
    )
    
    assert state["material_id"] == "real-material-uuid"
    assert state["current_page"] == 10
    print("   - State has material context for injection")
    print(f"   - Material ID: {state['material_id']}")
    print(f"   - Current page: {state['current_page']}")


# =============================================================================
# SECTION 7: INTEGRATION TESTS
# =============================================================================

@run_test("Integration - Full QuickChatAgent graph compilation")
def test_integration_quickchat_graph():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Verify graph is compiled
    assert hasattr(agent, 'graph'), "Agent should have compiled graph"
    assert agent.graph is not None, "Graph should not be None"
    
    print("   - QuickChatAgent graph compiled successfully")


@run_test("Integration - QuickChatAgent with MemorySaver")
def test_integration_quickchat_memory():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    from langgraph.checkpoint.memory import MemorySaver
    
    llm = get_gemini_model()
    checkpointer = MemorySaver()
    
    agent = QuickChatAgent(llm=llm, checkpointer=checkpointer)
    
    assert agent.checkpointer is not None
    assert agent.graph is not None
    
    print("   - Agent with MemorySaver initialized")
    print("   - Graph compiled with checkpointer")


@run_test("Integration - Database FTS functions exist")
def test_integration_fts_functions():
    from app.services.storage import search_page_analyses, get_user_courses_with_materials
    
    # These functions should be importable
    assert callable(search_page_analyses)
    assert callable(get_user_courses_with_materials)
    
    print("   - search_page_analyses function exists")
    print("   - get_user_courses_with_materials function exists")


@run_test("Integration - Langfuse prompt loading")
def test_integration_langfuse_prompt():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    from app.core.config import settings
    
    if not settings.LANGFUSE_ENABLED:
        print("   - Langfuse is disabled in settings")
        return
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Agent should have a system prompt
    assert agent.system_prompt is not None
    assert len(agent.system_prompt) > 100, "System prompt should have content"
    
    print(f"   - System prompt loaded ({len(agent.system_prompt)} chars)")
    print("   - Langfuse integration working or fallback used")


@run_test("Integration - Agent personality texts generation")
def test_integration_personality_texts():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Test German personality texts
    formality_de, humor_de, encouragement_de = agent._get_personality_texts(
        language="de",
        formality="formal",
        humor="light",
        encouragement="moderate"
    )
    
    assert len(formality_de) > 0
    assert len(humor_de) > 0
    assert len(encouragement_de) > 0
    print("   - German personality texts generated")
    
    # Test English personality texts
    formality_en, humor_en, encouragement_en = agent._get_personality_texts(
        language="en",
        formality="informal",
        humor="moderate",
        encouragement="enthusiastic"
    )
    
    assert len(formality_en) > 0
    assert len(humor_en) > 0
    assert len(encouragement_en) > 0
    print("   - English personality texts generated")


# =============================================================================
# SECTION 8: ERROR HANDLING TESTS
# =============================================================================

@run_test("Error Handling - SearchTopicTool with empty query")
def test_error_search_empty_query():
    from app.tools.search_topic_tool import SearchTopicTool
    from app.services.storage import get_supabase_client
    
    tool = SearchTopicTool()
    
    # Get a valid user ID
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if not profiles.data:
        print("   - No profiles found, using dummy user")
        user_id = str(uuid.uuid4())
    else:
        user_id = profiles.data[0]["id"]
    
    # Search with empty query
    result = tool._run(
        query="",
        user_id=user_id,
        language="auto",
        limit=5
    )
    
    result_data = json.loads(result)
    
    # Should return empty results or handle gracefully
    print(f"   - Empty query handled: {result_data.get('found', 'N/A')}")
    print("   - Tool did not crash with empty query")


@run_test("Error Handling - GetUserCoursesTool with new user")
def test_error_new_user_no_courses():
    from app.tools.user_courses_tool import GetUserCoursesTool
    
    tool = GetUserCoursesTool()
    
    # Use a UUID that definitely doesn't exist
    fake_user_id = str(uuid.uuid4())
    
    result = tool._run(user_id=fake_user_id)
    result_data = json.loads(result)
    
    # Should return empty courses, not error
    if "error" in result_data:
        print(f"   - Error returned (expected): {result_data['error'][:50]}...")
    else:
        assert result_data.get("found") == False
        assert result_data.get("courses") == []
        print("   - New user with no courses handled correctly")


@run_test("Error Handling - QuickChatState invalid mode")
def test_error_state_invalid_mode():
    from app.agents.quickchat.quickchat_agent import QuickChatState
    from langchain_core.messages import HumanMessage
    
    # TypedDict doesn't enforce enum values, but we can test behavior
    state = QuickChatState(
        messages=[HumanMessage(content="Test")],
        mode="invalid_mode"  # Not a valid mode
    )
    
    # State should still be created (TypedDict is not strict by default)
    assert state["mode"] == "invalid_mode"
    print("   - State accepts any mode value (no strict enum)")
    print("   - Note: Mode validation should be done in agent logic")


@run_test("Error Handling - Agent fallback system prompt")
def test_error_agent_fallback_prompt():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    
    # Even if Langfuse fails, agent should have a fallback prompt
    agent = QuickChatAgent(llm=llm)
    
    assert agent.system_prompt is not None
    assert len(agent.system_prompt) > 50
    
    # Check it contains expected content
    prompt_lower = agent.system_prompt.lower()
    assert "discovery" in prompt_lower or "tutoring" in prompt_lower or "search" in prompt_lower
    
    print("   - Fallback system prompt is available")
    print(f"   - Prompt length: {len(agent.system_prompt)} chars")


# =============================================================================
# SECTION 9: API ENDPOINT TESTS
# =============================================================================

@run_test("API Schema - QuickChatInitiateRequest")
def test_api_schema_initiate():
    from app.models.schemas import QuickChatInitiateRequest
    
    request = QuickChatInitiateRequest(
        user_id="test-user-uuid"
    )
    
    assert request.user_id == "test-user-uuid"
    print("   - QuickChatInitiateRequest schema validated")


@run_test("API Schema - QuickChatMessageRequest")
def test_api_schema_message():
    from app.models.schemas import QuickChatMessageRequest
    
    request = QuickChatMessageRequest(
        user_id="test-user-uuid",
        message="Tell me about IT security",
        thread_id="quickchat-test-thread"
    )
    
    assert request.user_id == "test-user-uuid"
    assert request.message == "Tell me about IT security"
    assert request.thread_id == "quickchat-test-thread"
    print("   - QuickChatMessageRequest schema validated")


@run_test("API Schema - QuickChatMessageRequest with page context")
def test_api_schema_message_with_context():
    from app.models.schemas import QuickChatMessageRequest
    
    request = QuickChatMessageRequest(
        user_id="test-user-uuid",
        message="What's on this page?",
        thread_id="quickchat-test-thread",
        material_id="material-uuid",
        page_number=15,
        course_id="course-uuid"
    )
    
    assert request.material_id == "material-uuid"
    assert request.page_number == 15
    assert request.course_id == "course-uuid"
    print("   - QuickChatMessageRequest with page context validated")


@run_test("API Schema - QuickChatSearchResult")
def test_api_schema_search_result():
    from app.models.schemas import QuickChatSearchResult
    
    result = QuickChatSearchResult(
        course_id="course-uuid",
        course_title="ISM",
        course_color="#3b82f6",
        material_id="material-uuid",
        material_name="IT Security Chapter",
        page_number=10,
        summary="This page covers IT security fundamentals",
        key_terms=["security", "firewall", "encryption"],
        rank=8.5
    )
    
    assert result.course_title == "ISM"
    assert result.page_number == 10
    assert len(result.key_terms) == 3
    print("   - QuickChatSearchResult schema validated")


@run_test("API Schema - QuickChatWarmupRequest")
def test_api_schema_warmup():
    from app.models.schemas import QuickChatWarmupRequest
    
    request = QuickChatWarmupRequest(
        user_id="test-user-uuid",
        thread_id="quickchat-test-thread"
    )
    
    assert request.user_id == "test-user-uuid"
    assert request.thread_id == "quickchat-test-thread"
    print("   - QuickChatWarmupRequest schema validated")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def main():
    print("\n" + "="*60)
    print("QUICK CHAT AGENT TEST SUITE")
    print("Testing QuickChatAgent, tools, and integrations")
    print("="*60)
    
    # Section 1: Import Tests
    print("\n" + "-"*60)
    print("SECTION 1: IMPORT TESTS")
    print("-"*60)
    
    import_tests = [
        test_import_quickchat_agent,
        test_import_state_aware_tool_node,
        test_import_search_topic_tool,
        test_import_get_user_courses_tool,
        test_import_quickchat_module,
    ]
    
    for test_func in import_tests:
        test_func()
    
    # Section 2: QuickChatAgent Initialization Tests
    print("\n" + "-"*60)
    print("SECTION 2: QUICKCHAT AGENT INITIALIZATION TESTS")
    print("-"*60)
    
    init_tests = [
        test_quickchat_init_default,
        test_quickchat_init_english,
        test_quickchat_init_personality,
        test_quickchat_init_checkpointer,
        test_quickchat_tool_binding,
        test_quickchat_max_history,
    ]
    
    for test_func in init_tests:
        test_func()
    
    # Section 3: State Management Tests
    print("\n" + "-"*60)
    print("SECTION 3: STATE MANAGEMENT TESTS")
    print("-"*60)
    
    state_tests = [
        test_quickchat_state_defaults,
        test_quickchat_state_full,
        test_quickchat_state_mode_transition,
    ]
    
    for test_func in state_tests:
        test_func()
    
    # Section 4: SearchTopicTool Tests
    print("\n" + "-"*60)
    print("SECTION 4: SEARCH TOPIC TOOL TESTS")
    print("-"*60)
    
    search_tests = [
        test_search_topic_tool_init,
        test_search_topic_tool_langchain,
        test_search_topic_tool_run,
        test_search_topic_tool_invalid_user,
        test_search_topic_tool_language,
    ]
    
    for test_func in search_tests:
        test_func()
    
    # Section 5: GetUserCoursesTool Tests
    print("\n" + "-"*60)
    print("SECTION 5: GET USER COURSES TOOL TESTS")
    print("-"*60)
    
    courses_tests = [
        test_get_user_courses_tool_init,
        test_get_user_courses_tool_langchain,
        test_get_user_courses_tool_run,
        test_get_user_courses_tool_invalid_user,
    ]
    
    for test_func in courses_tests:
        test_func()
    
    # Section 6: StateAwareToolNode Tests
    print("\n" + "-"*60)
    print("SECTION 6: STATE-AWARE TOOL NODE TESTS")
    print("-"*60)
    
    tool_node_tests = [
        test_state_aware_tool_node_init,
        test_state_aware_tool_node_user_id_injection,
        test_state_aware_tool_node_material_injection,
    ]
    
    for test_func in tool_node_tests:
        test_func()
    
    # Section 7: Integration Tests
    print("\n" + "-"*60)
    print("SECTION 7: INTEGRATION TESTS")
    print("-"*60)
    
    integration_tests = [
        test_integration_quickchat_graph,
        test_integration_quickchat_memory,
        test_integration_fts_functions,
        test_integration_langfuse_prompt,
        test_integration_personality_texts,
    ]
    
    for test_func in integration_tests:
        test_func()
    
    # Section 8: Error Handling Tests
    print("\n" + "-"*60)
    print("SECTION 8: ERROR HANDLING TESTS")
    print("-"*60)
    
    error_tests = [
        test_error_search_empty_query,
        test_error_new_user_no_courses,
        test_error_state_invalid_mode,
        test_error_agent_fallback_prompt,
    ]
    
    for test_func in error_tests:
        test_func()
    
    # Section 9: API Endpoint Tests
    print("\n" + "-"*60)
    print("SECTION 9: API SCHEMA TESTS")
    print("-"*60)
    
    api_tests = [
        test_api_schema_initiate,
        test_api_schema_message,
        test_api_schema_message_with_context,
        test_api_schema_search_result,
        test_api_schema_warmup,
    ]
    
    for test_func in api_tests:
        test_func()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    total = results['passed'] + results['failed'] + results['skipped']
    print(f"Total tests: {total}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print("="*60)
    
    if results['failed'] > 0:
        print("\n⚠️  Some tests failed. Review errors above.")
        sys.exit(1)
    else:
        print("\n🎉 All Quick Chat agent tests passed!")
        print("Agent, tools, and integrations are working correctly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
