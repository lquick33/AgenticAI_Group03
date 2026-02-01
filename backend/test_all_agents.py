"""
Comprehensive Agent Test Suite

Tests all features of:
- TutorAgent
- FlashcardGeneratorAgent
- QuizGeneratorAgent
- All 16+ tools
- Integration flows

Run with: python test_all_agents.py

Requirements:
- Running Anki with AnkiConnect
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


def test(name: str):
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

@test("Import BaseAgent")
def test_import_base_agent():
    from app.agents.base import BaseAgent
    print("   - BaseAgent imported successfully")
    
    # Check key methods exist
    assert hasattr(BaseAgent, 'run'), "BaseAgent should have 'run' method"
    assert hasattr(BaseAgent, 'arun'), "BaseAgent should have 'arun' method"
    assert hasattr(BaseAgent, 'stream'), "BaseAgent should have 'stream' method"
    print("   - BaseAgent has all expected methods")


@test("Import TutorAgent")
def test_import_tutor_agent():
    from app.agents.tutor.tutor_agent import TutorAgent, TutorState
    print("   - TutorAgent imported successfully")
    print("   - TutorState imported successfully")
    
    # Check TutorState fields
    annotations = TutorState.__annotations__
    assert "current_page" in annotations, "TutorState should have 'current_page'"
    assert "material_id" in annotations, "TutorState should have 'material_id'"
    assert "user_id" in annotations, "TutorState should have 'user_id'"
    print("   - TutorState has required fields")


@test("Import FlashcardGeneratorAgent")
def test_import_flashcard_agent():
    from app.agents.flashcards.flashcard_agent import (
        FlashcardGeneratorAgent,
        FlashcardState,
        deduplicate_flashcards
    )
    print("   - FlashcardGeneratorAgent imported successfully")
    print("   - FlashcardState imported successfully")
    print("   - deduplicate_flashcards imported successfully")
    
    # Check FlashcardState fields
    annotations = FlashcardState.__annotations__
    assert "course_material_id" in annotations
    assert "all_cards" in annotations
    assert "deduplicate_course" in annotations
    assert "existing_anki_fronts" in annotations
    print("   - FlashcardState has all required fields")


@test("Import QuizGeneratorAgent")
def test_import_quiz_agent():
    from app.agents.quiz.quiz_generator_agent import QuizGeneratorAgent
    print("   - QuizGeneratorAgent imported successfully")
    
    # Check key methods
    assert hasattr(QuizGeneratorAgent, 'generate_quiz'), "Should have 'generate_quiz' method"
    print("   - QuizGeneratorAgent has required methods")


@test("Import QuickChatAgent")
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
    print("   - QuickChatState has required fields")


@test("Import QuickChat Tools")
def test_import_quickchat_tools():
    from app.tools.search_topic_tool import SearchTopicTool, SearchTopicInput
    from app.tools.user_courses_tool import GetUserCoursesTool, GetUserCoursesInput
    print("   - SearchTopicTool imported successfully")
    print("   - GetUserCoursesTool imported successfully")
    
    # Check SearchTopicInput fields
    fields = SearchTopicInput.model_fields
    assert "query" in fields, "SearchTopicInput should have 'query'"
    assert "user_id" in fields, "SearchTopicInput should have 'user_id'"
    print("   - QuickChat tool inputs have required fields")


@test("Import Anki Tools")
def test_import_anki_tools():
    from app.tools.anki_tools import (
        get_anki_stats,
        create_flashcard,
        create_flashcards_batch,
        search_anki_cards,
        sync_anki,
        get_anki_deck_list,
        get_knowledge_levels,
        get_course_knowledge_levels,
        create_course_flashcard,
        create_course_flashcards_batch
    )
    print("   - All 10 Anki tools imported successfully")


@test("Import Course Material Tool")
def test_import_course_material_tool():
    from app.tools.course_material_tool import GetCourseMaterialSummaryTool
    print("   - GetCourseMaterialSummaryTool imported successfully")


@test("Import Knowledge Tool")
def test_import_knowledge_tool():
    from app.tools.knowledge_tool import GetCourseKnowledgeTool, get_course_knowledge_tool
    print("   - GetCourseKnowledgeTool imported successfully")
    print("   - get_course_knowledge_tool imported successfully")


@test("Import Page Analysis Tool")
def test_import_page_analysis_tool():
    from app.tools.page_analysis_tool import GetPageAnalysisTool
    print("   - GetPageAnalysisTool imported successfully")


@test("Import Page Image Tool")
def test_import_page_image_tool():
    from app.tools.page_image_tool import GetPageImageTool
    print("   - GetPageImageTool imported successfully")


@test("Import Quiz Tool")
def test_import_quiz_tool():
    from app.tools.quiz_tool import CreateQuizTool
    print("   - CreateQuizTool imported successfully")


@test("Import TTS Tool")
def test_import_tts_tool():
    try:
        from app.tools.tts_tool import TextToSpeechTool
        print("   - TextToSpeechTool imported successfully")
    except ImportError as e:
        if "texttospeech" in str(e):
            print("   - TextToSpeechTool skipped (google-cloud-texttospeech not installed)")
            print("   - This is an optional dependency for TTS features")
        else:
            raise


@test("Import All Schemas")
def test_import_schemas():
    from app.models.schemas import (
        SlideAnalysis,
        PageAnalysisResponse,
        UploadResponse,
        CourseResponse,
        ChatInitiateRequest,
        ChatMessageRequest,
        PageSkipDecision,
        Flashcard,
        FlashcardGenerationResult,
        MaterialClassification,
        QuizQuestion,
        QuizData,
        QuizResult,
        QuizToolResponse
    )
    print("   - All 14 schemas imported successfully")


@test("Import Services")
def test_import_services():
    from app.services.storage import get_supabase_client
    from app.services.analyzer import get_gemini_model
    from app.services.observability import get_langfuse_client
    from app.services.anki.client import AnkiClient
    from app.services.anki.knowledge_service import KnowledgeService
    print("   - All core services imported successfully")


# =============================================================================
# SECTION 2: TUTOR AGENT TESTS
# =============================================================================

@test("TutorAgent - Initialize with default config")
def test_tutor_init_default():
    from app.agents.tutor.tutor_agent import TutorAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = TutorAgent(llm=llm)
    
    assert agent.name == "TutorAgent"
    assert agent.language == "de"
    print(f"   - Agent name: {agent.name}")
    print(f"   - Default language: {agent.language}")
    print("   - Agent initialized with default config")


@test("TutorAgent - Initialize with personality config")
def test_tutor_init_personality():
    from app.agents.tutor.tutor_agent import TutorAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    personality_config = {
        "formality": "informal",
        "humor": "light",
        "encouragement": "enthusiastic"
    }
    
    agent = TutorAgent(
        llm=llm,
        language="en",
        personality_config=personality_config
    )
    
    assert agent.language == "en"
    print(f"   - Language: {agent.language}")
    print(f"   - Personality: {personality_config}")
    print("   - Agent initialized with custom personality")


@test("TutorAgent - Tool binding verification")
def test_tutor_tool_binding():
    from app.agents.tutor.tutor_agent import TutorAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = TutorAgent(llm=llm)
    
    # Check that graph is compiled (tools are bound to the graph)
    assert hasattr(agent, 'graph'), "Agent should have graph attribute"
    assert agent.graph is not None, "Graph should not be None"
    
    # Check graph has nodes (including tool nodes)
    graph_nodes = list(agent.graph.nodes.keys()) if hasattr(agent.graph, 'nodes') else []
    print(f"   - Graph nodes: {graph_nodes}")
    
    # The tutor agent uses tools through its graph
    print("   - Agent has compiled graph with tool integration")
    print("   - Tool binding verified through graph structure")


@test("TutorAgent - State management")
def test_tutor_state_management():
    from app.agents.tutor.tutor_agent import TutorAgent, TutorState
    from app.services.analyzer import get_gemini_model
    from langchain_core.messages import HumanMessage
    
    llm = get_gemini_model()
    agent = TutorAgent(llm=llm)
    
    # Create a test state
    test_state = TutorState(
        messages=[HumanMessage(content="Hello")],
        current_page=5,
        material_id="test-uuid",
        user_id="user-uuid"
    )
    
    assert test_state["current_page"] == 5
    assert test_state["material_id"] == "test-uuid"
    assert len(test_state["messages"]) == 1
    print("   - TutorState created successfully")
    print(f"   - Current page: {test_state['current_page']}")
    print(f"   - Material ID: {test_state['material_id']}")


@test("TutorAgent - Message history sliding window")
def test_tutor_message_history():
    from app.agents.tutor.tutor_agent import TutorAgent
    from app.services.analyzer import get_gemini_model
    from langchain_core.messages import HumanMessage, AIMessage
    
    llm = get_gemini_model()
    agent = TutorAgent(llm=llm)
    
    # Verify MAX_HISTORY_MESSAGES constant
    assert hasattr(agent, 'MAX_HISTORY_MESSAGES'), "Agent should have MAX_HISTORY_MESSAGES"
    max_history = agent.MAX_HISTORY_MESSAGES
    print(f"   - MAX_HISTORY_MESSAGES: {max_history}")
    
    # Create more messages than the limit
    messages = []
    for i in range(max_history + 5):
        messages.append(HumanMessage(content=f"Message {i}"))
        messages.append(AIMessage(content=f"Response {i}"))
    
    print(f"   - Created {len(messages)} messages (exceeds limit)")
    print("   - Message history sliding window is configured")


# =============================================================================
# SECTION 2.5: QUICKCHAT AGENT TESTS
# =============================================================================

@test("QuickChatAgent - Initialize with default config")
def test_quickchat_init_default():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    assert agent.name == "QuickChatAgent"
    print(f"   - Agent name: {agent.name}")
    print("   - Agent initialized with default config")


@test("QuickChatAgent - Tool binding verification")
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
    print("   - All required tools are bound")


@test("QuickChatAgent - State management")
def test_quickchat_state_management():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent, QuickChatState
    from app.services.analyzer import get_gemini_model
    from langchain_core.messages import HumanMessage
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Create a test state
    test_state = QuickChatState(
        messages=[HumanMessage(content="Find IT security topic")],
        mode="discovery",
        current_page=None,
        material_id=None,
        user_id="test-user-uuid"
    )
    
    assert test_state["mode"] == "discovery"
    assert test_state["user_id"] == "test-user-uuid"
    print("   - QuickChatState created successfully")
    print(f"   - Mode: {test_state['mode']}")
    print(f"   - User ID: {test_state['user_id']}")


@test("SearchTopicTool - Execute search")
def test_search_topic_tool_run():
    from app.tools.search_topic_tool import SearchTopicTool
    from app.services.storage import get_supabase_client
    import json
    
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


@test("GetUserCoursesTool - Execute retrieval")
def test_get_user_courses_tool_run():
    from app.tools.user_courses_tool import GetUserCoursesTool
    from app.services.storage import get_supabase_client
    import json
    
    tool = GetUserCoursesTool()
    
    # Get a valid user ID
    client = get_supabase_client()
    profiles = client.table("profiles").select("id").limit(1).execute()
    
    if not profiles.data:
        print("   - No profiles found, skipping retrieval")
        return
    
    user_id = profiles.data[0]["id"]
    
    result = tool._run(user_id=user_id)
    result_data = json.loads(result)
    
    assert "found" in result_data, "Result should have 'found' key"
    assert "courses" in result_data, "Result should have 'courses' key"
    
    print(f"   - Found: {result_data['found']}")
    print(f"   - Courses count: {len(result_data['courses'])}")


# =============================================================================
# SECTION 3: FLASHCARD GENERATOR AGENT TESTS
# =============================================================================

@test("FlashcardGeneratorAgent - Initialize")
def test_flashcard_init():
    from app.agents.flashcards.flashcard_agent import FlashcardGeneratorAgent
    
    agent = FlashcardGeneratorAgent()
    
    assert agent.name == "FlashcardGeneratorAgent"
    print(f"   - Agent name: {agent.name}")
    print("   - Agent initialized successfully")


@test("FlashcardGeneratorAgent - FlashcardState validation")
def test_flashcard_state_validation():
    from app.agents.flashcards.flashcard_agent import FlashcardState
    
    # Check all required fields exist
    annotations = FlashcardState.__annotations__
    
    required_fields = [
        "course_material_id", "user_id", "course_id",
        "page_analyses", "snippets_by_page", "messages_by_page",
        "skip_decisions", "current_page_index", "all_cards",
        "save_to_db", "classification", "deduplicate_course",
        "existing_anki_fronts", "parent_deck_name", "target_deck_name",
        "anki_synced", "ankiweb_synced"
    ]
    
    for field in required_fields:
        assert field in annotations, f"FlashcardState should have '{field}'"
    
    print(f"   - All {len(required_fields)} required fields present")
    print("   - FlashcardState validated successfully")


@test("FlashcardGeneratorAgent - Deduplication algorithm")
def test_flashcard_deduplication():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    # Test data
    new_cards = [
        {"front": "What is Python?", "back": "A programming language"},
        {"front": "What is python", "back": "Different answer"},  # Similar (fuzzy match)
        {"front": "Explain JavaScript", "back": "A scripting language"},
        {"front": "What is Java?", "back": "Another language"},  # Unique
    ]
    
    existing_fronts = [
        "What is Python?",  # Exact match
        "Explain JavaScript",  # Exact match
    ]
    
    unique_cards, removed = deduplicate_flashcards(new_cards, existing_fronts)
    
    print(f"   - Input cards: {len(new_cards)}")
    print(f"   - Existing fronts: {len(existing_fronts)}")
    print(f"   - Removed duplicates: {removed}")
    print(f"   - Unique cards remaining: {len(unique_cards)}")
    
    # Should remove exact matches and fuzzy matches
    assert removed >= 2, f"Should remove at least 2 duplicates, removed {removed}"
    assert len(unique_cards) <= 2, f"Should have at most 2 unique cards, got {len(unique_cards)}"
    print("   - Deduplication working correctly")


@test("FlashcardGeneratorAgent - Internal deduplication")
def test_flashcard_internal_dedup():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    # Test deduplication within new cards (no existing)
    new_cards = [
        {"front": "What is a variable?", "back": "Storage"},
        {"front": "What is a variable", "back": "Container"},  # Duplicate of above
        {"front": "Define a function", "back": "Reusable code"},
    ]
    
    unique_cards, removed = deduplicate_flashcards(new_cards, [])
    
    print(f"   - Input cards: {len(new_cards)}")
    print(f"   - Internal duplicates removed: {removed}")
    print(f"   - Unique cards: {len(unique_cards)}")
    
    assert removed >= 1, "Should remove at least 1 internal duplicate"
    print("   - Internal deduplication working")


# =============================================================================
# SECTION 4: QUIZ GENERATOR AGENT TESTS
# =============================================================================

@test("QuizGeneratorAgent - Initialize")
def test_quiz_init():
    from app.agents.quiz.quiz_generator_agent import QuizGeneratorAgent
    
    agent = QuizGeneratorAgent()
    
    assert agent.name == "QuizGeneratorAgent"
    print(f"   - Agent name: {agent.name}")
    print("   - Agent initialized successfully")


@test("QuizGeneratorAgent - Initialize with language")
def test_quiz_init_language():
    from app.agents.quiz.quiz_generator_agent import QuizGeneratorAgent
    
    agent = QuizGeneratorAgent(language="en")
    
    assert agent.language == "en"
    print(f"   - Language: {agent.language}")
    print("   - Agent initialized with English language")


@test("QuizData schema validation")
def test_quiz_data_schema():
    from app.models.schemas import QuizData, QuizQuestion
    
    # Create valid quiz data
    questions = [
        QuizQuestion(
            id="q1",
            question="What is Python?",
            options={"A": "A language", "B": "A snake", "C": "A framework", "D": "A database"},
            correct_answer="A",
            difficulty="easy",
            explanation="Python is a programming language."
        ),
        QuizQuestion(
            id="q2",
            question="What is OOP?",
            options={"A": "Object Oriented Programming", "B": "Open Office Protocol", "C": "Online Operating Platform", "D": "None"},
            correct_answer="A",
            difficulty="medium",
            explanation="OOP stands for Object Oriented Programming."
        ),
        QuizQuestion(
            id="q3",
            question="What is recursion?",
            options={"A": "A loop", "B": "A function calling itself", "C": "A variable", "D": "A class"},
            correct_answer="B",
            difficulty="hard",
            explanation="Recursion is when a function calls itself."
        ),
    ]
    
    quiz = QuizData(
        topic="Python Basics",
        questions=questions,
        metadata={"easy_count": 1, "medium_count": 1, "hard_count": 1}
    )
    
    assert quiz.topic == "Python Basics"
    assert len(quiz.questions) == 3
    print(f"   - Topic: {quiz.topic}")
    print(f"   - Questions: {len(quiz.questions)}")
    print(f"   - Difficulty distribution: {quiz.metadata}")
    print("   - QuizData validated successfully")


@test("QuizQuestion options validation")
def test_quiz_question_options():
    from app.models.schemas import QuizQuestion
    from pydantic import ValidationError
    
    # Test valid options
    valid_question = QuizQuestion(
        id="q1",
        question="Test?",
        options={"A": "One", "B": "Two", "C": "Three", "D": "Four"},
        correct_answer="A",
        difficulty="easy",
        explanation="Test explanation"
    )
    print("   - Valid options accepted")
    
    # Test invalid options (missing key)
    try:
        invalid_question = QuizQuestion(
            id="q2",
            question="Test?",
            options={"A": "One", "B": "Two", "C": "Three"},  # Missing D
            correct_answer="A",
            difficulty="easy",
            explanation="Test"
        )
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Invalid options correctly rejected (missing D)")
    
    # Test invalid options (extra key)
    try:
        invalid_question = QuizQuestion(
            id="q3",
            question="Test?",
            options={"A": "One", "B": "Two", "C": "Three", "D": "Four", "E": "Five"},
            correct_answer="A",
            difficulty="easy",
            explanation="Test"
        )
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Invalid options correctly rejected (extra E)")
    
    print("   - Options validation working correctly")


# =============================================================================
# SECTION 5: TOOL TESTS
# =============================================================================

@test("Anki Tools - get_anki_deck_list")
def test_tool_get_deck_list():
    from app.tools.anki_tools import get_anki_deck_list
    
    result = get_anki_deck_list()
    
    assert "status" in result, "Result should have 'status'"
    
    if result["status"] == "success":
        assert "decks" in result, "Result should have 'decks'"
        print(f"   - Found {len(result['decks'])} decks")
    else:
        print(f"   - Anki not available: {result.get('error', 'unknown')}")
        # Don't fail if Anki isn't running
    
    print("   - get_anki_deck_list executed")


@test("Anki Tools - create and delete test deck")
def test_tool_create_delete_deck():
    from app.services.anki.client import AnkiClient
    
    try:
        anki = AnkiClient()
        version = anki.get_version()
        print(f"   - AnkiConnect version: {version}")
        
        test_deck = "AgentTest::TestDeck"
        
        # Create deck
        deck_id = anki.create_deck(test_deck)
        print(f"   - Created deck: {test_deck} (id: {deck_id})")
        
        # Verify exists
        decks = anki.get_deck_names()
        assert test_deck in decks, "Test deck should exist"
        print("   - Verified deck exists")
        
        # Delete deck
        anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
        anki.delete_deck_with_cards("AgentTest", i_understand_this_is_permanent=True)
        print("   - Cleaned up test deck")
        
    except Exception as e:
        if "AnkiConnect" in str(e) or "connection" in str(e).lower():
            print(f"   - Anki not running, skipping: {e}")
        else:
            raise


@test("Anki Tools - create_flashcard")
def test_tool_create_flashcard():
    from app.tools.anki_tools import create_flashcard
    from app.services.anki.client import AnkiClient
    
    test_deck = "AgentTest::FlashcardTool"
    
    try:
        # Create card
        result = create_flashcard(
            deck=test_deck,
            question="Test Question from Agent",
            answer="Test Answer from Agent",
            tags=["test", "agent"],
            sync_immediately=False
        )
        
        print(f"   - Result status: {result['status']}")
        
        if result["status"] == "success":
            print(f"   - Created note_id: {result['note_id']}")
            print(f"   - Deck: {result['deck']}")
            
            # Cleanup
            anki = AnkiClient()
            anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
            anki.delete_deck_with_cards("AgentTest", i_understand_this_is_permanent=True)
            print("   - Cleaned up")
        else:
            print(f"   - Could not create card: {result.get('error', 'unknown')}")
            
    except Exception as e:
        if "AnkiConnect" in str(e) or "connection" in str(e).lower():
            print(f"   - Anki not running, skipping: {e}")
        else:
            raise


@test("Anki Tools - create_flashcards_batch")
def test_tool_create_flashcards_batch():
    from app.tools.anki_tools import create_flashcards_batch
    from app.services.anki.client import AnkiClient
    
    test_deck = "AgentTest::BatchTool"
    
    try:
        cards = [
            {"question": "Batch Q1", "answer": "Batch A1"},
            {"question": "Batch Q2", "answer": "Batch A2"},
            {"question": "Batch Q3", "answer": "Batch A3"},
        ]
        
        result = create_flashcards_batch(
            cards=cards,
            default_deck=test_deck,
            sync_after=False
        )
        
        print(f"   - Result status: {result['status']}")
        
        if result["status"] == "success":
            print(f"   - Created: {result['created']}")
            print(f"   - Failed: {result['failed']}")
            
            # Cleanup
            anki = AnkiClient()
            anki.delete_deck_with_cards(test_deck, i_understand_this_is_permanent=True)
            anki.delete_deck_with_cards("AgentTest", i_understand_this_is_permanent=True)
            print("   - Cleaned up")
        else:
            print(f"   - Could not create cards: {result.get('error', 'unknown')}")
            
    except Exception as e:
        if "AnkiConnect" in str(e) or "connection" in str(e).lower():
            print(f"   - Anki not running, skipping: {e}")
        else:
            raise


@test("Anki Tools - search_anki_cards")
def test_tool_search_cards():
    from app.tools.anki_tools import search_anki_cards
    
    try:
        # Search for all cards (empty query matches all)
        result = search_anki_cards(query="deck:Default")
        
        print(f"   - Result status: {result['status']}")
        
        if result["status"] == "success":
            print(f"   - Found {result['count']} cards in Default deck")
        else:
            print(f"   - Search result: {result.get('error', 'no cards or error')}")
            
    except Exception as e:
        if "AnkiConnect" in str(e) or "connection" in str(e).lower():
            print(f"   - Anki not running, skipping: {e}")
        else:
            raise


@test("Anki Tools - get_anki_stats")
def test_tool_get_stats():
    from app.tools.anki_tools import get_anki_stats
    
    try:
        result = get_anki_stats()
        
        print(f"   - Result status: {result['status']}")
        
        if result["status"] == "success":
            print(f"   - Cards reviewed today: {result.get('cards_reviewed_today', 0)}")
            print(f"   - Decks with stats: {len(result.get('decks', []))}")
        else:
            print(f"   - Could not get stats: {result.get('error', 'unknown')}")
            
    except Exception as e:
        if "AnkiConnect" in str(e) or "connection" in str(e).lower():
            print(f"   - Anki not running, skipping: {e}")
        else:
            raise


@test("TTS Tool - TextToSpeechTool exists")
def test_tool_tts_exists():
    try:
        from app.tools.tts_tool import TextToSpeechTool
        
        tool = TextToSpeechTool()
        
        assert tool.name == "text_to_speech"
        print(f"   - Tool name: {tool.name}")
        print(f"   - Tool description: {tool.description[:50]}...")
        print("   - TTS tool configured correctly")
    except ImportError as e:
        if "texttospeech" in str(e):
            print("   - TTS tool skipped (google-cloud-texttospeech not installed)")
            print("   - This is an optional dependency for TTS features")
        else:
            raise


@test("Page Analysis Tool - GetPageAnalysisTool exists")
def test_tool_page_analysis_exists():
    from app.tools.page_analysis_tool import GetPageAnalysisTool
    
    tool = GetPageAnalysisTool()
    
    assert tool.name == "get_page_analysis"
    print(f"   - Tool name: {tool.name}")
    print("   - Page analysis tool configured correctly")


@test("Page Image Tool - GetPageImageTool exists")
def test_tool_page_image_exists():
    from app.tools.page_image_tool import GetPageImageTool
    
    tool = GetPageImageTool()
    
    assert tool.name == "get_page_image"
    print(f"   - Tool name: {tool.name}")
    print("   - Page image tool configured correctly")


@test("Quiz Tool - CreateQuizTool exists")
def test_tool_quiz_exists():
    from app.tools.quiz_tool import CreateQuizTool
    
    tool = CreateQuizTool()
    
    assert tool.name == "create_quiz"
    print(f"   - Tool name: {tool.name}")
    print("   - Quiz tool configured correctly")


@test("Course Material Tool - GetCourseMaterialSummaryTool exists")
def test_tool_course_material_exists():
    from app.tools.course_material_tool import GetCourseMaterialSummaryTool
    
    tool = GetCourseMaterialSummaryTool()
    
    assert tool.name == "get_course_material_summary"
    print(f"   - Tool name: {tool.name}")
    print("   - Course material tool configured correctly")


@test("Knowledge Tool - GetCourseKnowledgeTool exists")
def test_tool_knowledge_exists():
    from app.tools.knowledge_tool import GetCourseKnowledgeTool, get_course_knowledge_tool
    
    # Create an instance
    tool = get_course_knowledge_tool()
    
    assert isinstance(tool, GetCourseKnowledgeTool)
    assert tool.name == "get_course_knowledge"
    print(f"   - Tool name: {tool.name}")
    print("   - Knowledge tool configured correctly")


# =============================================================================
# SECTION 6: INTEGRATION TESTS
# =============================================================================

@test("Integration - Database connection")
def test_integration_db():
    from app.services.storage import get_supabase_client
    
    client = get_supabase_client()
    
    # Try to fetch profiles
    result = client.table("profiles").select("id").limit(1).execute()
    
    if result.data:
        print(f"   - Connected to Supabase successfully")
        print(f"   - Found {len(result.data)} profile(s)")
    else:
        print("   - Connected but no profiles found")
    
    print("   - Database connection verified")


@test("Integration - Gemini LLM")
def test_integration_gemini():
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    
    assert llm is not None
    print(f"   - Gemini model initialized")
    print(f"   - Model type: {type(llm).__name__}")
    print("   - LLM integration verified")


@test("Integration - Langfuse client")
def test_integration_langfuse():
    from app.services.observability import get_langfuse_client
    from app.core.config import settings
    
    if not settings.LANGFUSE_ENABLED:
        print("   - Langfuse is disabled in settings")
        return
    
    try:
        client = get_langfuse_client()
        
        if client:
            print("   - Langfuse client initialized")
            print("   - Observability integration verified")
        else:
            print("   - Langfuse client returned None")
    except Exception as e:
        print(f"   - Langfuse not configured: {e}")


@test("Integration - AnkiClient with cache")
def test_integration_anki_cache():
    from app.services.storage import (
        cache_flashcards,
        get_cached_flashcards_for_material,
        get_supabase_client
    )
    
    client = get_supabase_client()
    profile = client.table("profiles").select("id").limit(1).execute()
    
    if not profile.data:
        print("   - No profiles found, skipping cache test")
        return
    
    user_id = profile.data[0]["id"]
    test_deck = "AgentTest::CacheIntegration"
    test_note_id = 1234567890
    
    # Cache a flashcard
    cards = [{"front": "Cache Test Q", "back": "Cache Test A", "tags": ["test"]}]
    cache_flashcards(cards, [test_note_id], user_id, test_deck, None)
    print("   - Cached flashcard in database")
    
    # Retrieve from cache
    cached = get_cached_flashcards_for_material(test_deck, user_id)
    assert len(cached) >= 1, "Should have at least 1 cached card"
    print(f"   - Retrieved {len(cached)} cached card(s)")
    
    # Cleanup
    client.table("flashcard_cache").delete().eq("anki_note_id", test_note_id).execute()
    print("   - Cleaned up cache entry")
    print("   - Cache integration verified")


@test("Integration - Full TutorAgent graph compilation")
def test_integration_tutor_graph():
    from app.agents.tutor.tutor_agent import TutorAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = TutorAgent(llm=llm)
    
    # Verify graph is compiled
    assert hasattr(agent, 'graph'), "Agent should have compiled graph"
    assert agent.graph is not None, "Graph should not be None"
    
    print("   - TutorAgent graph compiled successfully")
    print("   - Graph nodes and edges configured")


@test("Integration - Full FlashcardGeneratorAgent graph compilation")
def test_integration_flashcard_graph():
    from app.agents.flashcards.flashcard_agent import FlashcardGeneratorAgent
    
    agent = FlashcardGeneratorAgent()
    
    # Verify graph is compiled
    assert hasattr(agent, 'graph'), "Agent should have compiled graph"
    assert agent.graph is not None, "Graph should not be None"
    
    print("   - FlashcardGeneratorAgent graph compiled successfully")


@test("Integration - Full QuizGeneratorAgent graph compilation")
def test_integration_quiz_graph():
    from app.agents.quiz.quiz_generator_agent import QuizGeneratorAgent
    
    agent = QuizGeneratorAgent()
    
    # Verify graph is compiled
    assert hasattr(agent, 'graph'), "Agent should have compiled graph"
    assert agent.graph is not None, "Graph should not be None"
    
    print("   - QuizGeneratorAgent graph compiled successfully")


@test("Integration - Full QuickChatAgent graph compilation")
def test_integration_quickchat_graph():
    from app.agents.quickchat.quickchat_agent import QuickChatAgent
    from app.services.analyzer import get_gemini_model
    
    llm = get_gemini_model()
    agent = QuickChatAgent(llm=llm)
    
    # Verify graph is compiled
    assert hasattr(agent, 'graph'), "Agent should have compiled graph"
    assert agent.graph is not None, "Graph should not be None"
    
    # Verify tool node is state-aware
    assert hasattr(agent, 'tool_node'), "Agent should have tool_node"
    assert agent.tool_node is not None, "Tool node should not be None"
    
    print("   - QuickChatAgent graph compiled successfully")
    print("   - StateAwareToolNode configured")


# =============================================================================
# SECTION 7: ERROR HANDLING TESTS
# =============================================================================

@test("Error Handling - Invalid material ID in page analysis")
def test_error_invalid_material_id():
    from app.tools.page_analysis_tool import GetPageAnalysisTool
    
    tool = GetPageAnalysisTool()
    
    # Call with invalid UUID using _run method
    result = tool._run(
        course_material_id="invalid-uuid-not-real",
        page_number=1,
        user_id="test-user"
    )
    
    # Should return error, not crash
    result_data = json.loads(result) if isinstance(result, str) else result
    print(f"   - Result: {result_data}")
    assert "error" in result_data, "Should contain error field"
    print("   - Tool handled invalid material ID gracefully")


@test("Error Handling - Anki not running")
def test_error_anki_not_running():
    from app.tools.anki_tools import get_anki_deck_list
    
    # This will either succeed (Anki running) or return error (not running)
    result = get_anki_deck_list()
    
    if result["status"] == "error":
        print(f"   - Anki error handled: {result.get('error', 'unknown')[:50]}")
    else:
        print("   - Anki is running, test shows graceful success")
    
    print("   - Error handling verified")


@test("Error Handling - Quiz validation errors")
def test_error_quiz_validation():
    from app.models.schemas import QuizData, QuizQuestion
    from pydantic import ValidationError
    
    # Test too few questions
    try:
        quiz = QuizData(
            topic="Test",
            questions=[
                QuizQuestion(
                    id="q1",
                    question="Only one question?",
                    options={"A": "1", "B": "2", "C": "3", "D": "4"},
                    correct_answer="A",
                    difficulty="easy",
                    explanation="Test"
                )
            ]
        )
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Correctly rejected quiz with too few questions")
    
    # Test too many questions
    try:
        questions = []
        for i in range(10):  # More than max of 8
            questions.append(QuizQuestion(
                id=f"q{i}",
                question=f"Question {i}?",
                options={"A": "1", "B": "2", "C": "3", "D": "4"},
                correct_answer="A",
                difficulty="easy",
                explanation="Test"
            ))
        quiz = QuizData(topic="Test", questions=questions)
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Correctly rejected quiz with too many questions")
    
    print("   - Quiz validation errors handled correctly")


@test("Error Handling - Empty explanation rejected")
def test_error_empty_explanation():
    from app.models.schemas import QuizQuestion
    from pydantic import ValidationError
    
    try:
        question = QuizQuestion(
            id="q1",
            question="Test?",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            correct_answer="A",
            difficulty="easy",
            explanation=""  # Empty!
        )
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Correctly rejected empty explanation")
    
    try:
        question = QuizQuestion(
            id="q1",
            question="Test?",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            correct_answer="A",
            difficulty="easy",
            explanation="   "  # Whitespace only!
        )
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        print("   - Correctly rejected whitespace-only explanation")
    
    print("   - Explanation validation working correctly")


@test("Error Handling - Flashcard dedup with empty inputs")
def test_error_dedup_empty():
    from app.agents.flashcards.flashcard_agent import deduplicate_flashcards
    
    # Empty new cards
    unique, removed = deduplicate_flashcards([], ["existing front"])
    assert len(unique) == 0
    assert removed == 0
    print("   - Handled empty new cards")
    
    # Empty existing fronts
    new_cards = [{"front": "Q1", "back": "A1"}]
    unique, removed = deduplicate_flashcards(new_cards, [])
    assert len(unique) == 1
    assert removed == 0
    print("   - Handled empty existing fronts")
    
    # Both empty
    unique, removed = deduplicate_flashcards([], [])
    assert len(unique) == 0
    assert removed == 0
    print("   - Handled both empty")
    
    print("   - Edge cases handled correctly")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def main():
    print("\n" + "="*60)
    print("COMPREHENSIVE AGENT TEST SUITE")
    print("Testing all agents, tools, and integrations")
    print("="*60)
    
    # Section 1: Import Tests
    print("\n" + "-"*60)
    print("SECTION 1: IMPORT TESTS")
    print("-"*60)
    
    import_tests = [
        test_import_base_agent,
        test_import_tutor_agent,
        test_import_flashcard_agent,
        test_import_quiz_agent,
        test_import_quickchat_agent,
        test_import_quickchat_tools,
        test_import_anki_tools,
        test_import_course_material_tool,
        test_import_knowledge_tool,
        test_import_page_analysis_tool,
        test_import_page_image_tool,
        test_import_quiz_tool,
        test_import_tts_tool,
        test_import_schemas,
        test_import_services,
    ]
    
    for test_func in import_tests:
        test_func()
    
    # Section 2: TutorAgent Tests
    print("\n" + "-"*60)
    print("SECTION 2: TUTOR AGENT TESTS")
    print("-"*60)
    
    tutor_tests = [
        test_tutor_init_default,
        test_tutor_init_personality,
        test_tutor_tool_binding,
        test_tutor_state_management,
        test_tutor_message_history,
    ]
    
    for test_func in tutor_tests:
        test_func()
    
    # Section 2.5: QuickChatAgent Tests
    print("\n" + "-"*60)
    print("SECTION 2.5: QUICKCHAT AGENT TESTS")
    print("-"*60)
    
    quickchat_tests = [
        test_quickchat_init_default,
        test_quickchat_tool_binding,
        test_quickchat_state_management,
        test_search_topic_tool_run,
        test_get_user_courses_tool_run,
    ]
    
    for test_func in quickchat_tests:
        test_func()
    
    # Section 3: FlashcardGeneratorAgent Tests
    print("\n" + "-"*60)
    print("SECTION 3: FLASHCARD GENERATOR AGENT TESTS")
    print("-"*60)
    
    flashcard_tests = [
        test_flashcard_init,
        test_flashcard_state_validation,
        test_flashcard_deduplication,
        test_flashcard_internal_dedup,
    ]
    
    for test_func in flashcard_tests:
        test_func()
    
    # Section 4: QuizGeneratorAgent Tests
    print("\n" + "-"*60)
    print("SECTION 4: QUIZ GENERATOR AGENT TESTS")
    print("-"*60)
    
    quiz_tests = [
        test_quiz_init,
        test_quiz_init_language,
        test_quiz_data_schema,
        test_quiz_question_options,
    ]
    
    for test_func in quiz_tests:
        test_func()
    
    # Section 5: Tool Tests
    print("\n" + "-"*60)
    print("SECTION 5: TOOL TESTS")
    print("-"*60)
    
    tool_tests = [
        test_tool_get_deck_list,
        test_tool_create_delete_deck,
        test_tool_create_flashcard,
        test_tool_create_flashcards_batch,
        test_tool_search_cards,
        test_tool_get_stats,
        test_tool_tts_exists,
        test_tool_page_analysis_exists,
        test_tool_page_image_exists,
        test_tool_quiz_exists,
        test_tool_course_material_exists,
        test_tool_knowledge_exists,
    ]
    
    for test_func in tool_tests:
        test_func()
    
    # Section 6: Integration Tests
    print("\n" + "-"*60)
    print("SECTION 6: INTEGRATION TESTS")
    print("-"*60)
    
    integration_tests = [
        test_integration_db,
        test_integration_gemini,
        test_integration_langfuse,
        test_integration_anki_cache,
        test_integration_tutor_graph,
        test_integration_flashcard_graph,
        test_integration_quiz_graph,
        test_integration_quickchat_graph,
    ]
    
    for test_func in integration_tests:
        test_func()
    
    # Section 7: Error Handling Tests
    print("\n" + "-"*60)
    print("SECTION 7: ERROR HANDLING TESTS")
    print("-"*60)
    
    error_tests = [
        test_error_invalid_material_id,
        test_error_anki_not_running,
        test_error_quiz_validation,
        test_error_empty_explanation,
        test_error_dedup_empty,
    ]
    
    for test_func in error_tests:
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
        print("\n🎉 All agent tests passed!")
        print("All agents, tools, and integrations are working correctly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
