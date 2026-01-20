"""
Interactive Test Script for TutorAgent

This script provides an interactive REPL for testing the TutorAgent
with continuous conversation support and state management.

Usage:
    python test_tutor_agent.py

Commands:
    !page <number>     - Set current page number
    !material <id>     - Set material ID
    !user <id>         - Set user ID
    !history           - Show conversation history
    !clear             - Clear conversation (reset thread)
    !quit              - Exit the script
"""

import sys
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.tutor import TutorAgent
from app.services.analyzer import get_gemini_model
from langgraph.checkpoint.memory import MemorySaver


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 60)
    print("TutorAgent Interactive Test Script")
    print("=" * 60)
    print("\nCommands:")
    print("  !page <number>     - Set current page number")
    print("  !material <id>     - Set material ID")
    print("  !user <id>         - Set user ID")
    print("  !history           - Show conversation history")
    print("  !clear             - Clear conversation (reset thread)")
    print("  !help              - Show this help message")
    print("  !quit              - Exit the script")
    print("\n" + "=" * 60 + "\n")


def print_state_info(material_id: str, user_id: str, current_page: int, thread_id: str):
    """Print current state information."""
    print(f"[State] Material ID: {material_id}")
    print(f"[State] User ID: {user_id}")
    print(f"[State] Current Page: {current_page}")
    print(f"[State] Thread ID: {thread_id}\n")


def show_history(agent: TutorAgent, thread_id: str):
    """Show conversation history."""
    try:
        history = agent.get_conversation_history(thread_id)
        if not history:
            print("[Info] No conversation history found.\n")
            return
        
        print("\n" + "-" * 60)
        print("Conversation History:")
        print("-" * 60)
        
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        
        for i, msg in enumerate(history, 1):
            msg_type = msg.__class__.__name__
            
            # Format content based on message type
            if isinstance(msg, SystemMessage):
                prefix = "🔧 [System]"
            elif isinstance(msg, HumanMessage):
                prefix = "👤 [You]"
            elif isinstance(msg, AIMessage):
                prefix = "🤖 [Agent]"
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    prefix += " (called tool)"
            elif isinstance(msg, ToolMessage):
                prefix = "🔨 [Tool]"
            else:
                prefix = f"[{msg_type}]"
            
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            print(f"{i}. {prefix} {content}")
        
        print("-" * 60 + "\n")
    except Exception as e:
        print(f"[Error] Failed to retrieve history: {str(e)}\n")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()


def run_agent(
    agent: TutorAgent,
    message: str,
    thread_id: str,
    material_id: str,
    user_id: str,
    current_page: int
):
    """
    Run the agent with a message and state.
    
    Args:
        agent: TutorAgent instance
        message: User message
        thread_id: Thread ID for conversation
        material_id: Material ID for state
        user_id: User ID for state
        current_page: Current page number for state
        
    Returns:
        Agent response
    """
    try:
        # Configure for persistence
        config = {"configurable": {"thread_id": thread_id}}
        if user_id:
            config["configurable"]["user_id"] = user_id
        
        # Check if this is a new thread or existing thread
        snapshot = agent.graph.get_state(config)
        is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")
        
        # Prepare initial state with messages and custom fields
        # Always include state fields to ensure they're available for tool calls
        if is_new_thread:
            # New thread: include system message
            messages = []
            if agent.system_prompt:
                messages.append(SystemMessage(content=agent.system_prompt))
            messages.append(HumanMessage(content=message))
            initial_state = {
                "messages": messages,
                "current_page": current_page,
                "material_id": material_id,
                "user_id": user_id
            }
        else:
            # Existing thread: just add new message, but update state fields
            # This ensures state fields are always current
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "current_page": current_page,
                "material_id": material_id,
                "user_id": user_id
            }
        
        # Run the graph
        result = agent.graph.invoke(initial_state, config)
        
        # Extract response message
        if result and "messages" in result:
            messages = result["messages"]
            # Get the last non-human message (should be AI response)
            # Skip tool messages and human messages
            from langchain_core.messages import AIMessage, ToolMessage
            
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    # This is the AI response
                    return msg.content
                elif isinstance(msg, ToolMessage):
                    # Tool was executed, continue to find AI response
                    continue
            
            # Fallback: get any message with content
            for msg in reversed(messages):
                if hasattr(msg, 'content') and msg.content:
                    return msg.content
        
        return "No response generated"
        
    except KeyboardInterrupt:
        raise
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "GOOGLE_API_KEY" in error_msg or "API key" in error_msg.lower():
            raise Exception(
                "API key error. Make sure GOOGLE_API_KEY is set in your .env file."
            )
        elif "database" in error_msg.lower() or "supabase" in error_msg.lower():
            raise Exception(
                f"Database error: {error_msg}. "
                "Make sure SUPABASE_URL and SUPABASE_KEY are set correctly."
            )
        else:
            raise Exception(f"Error running agent: {error_msg}")


def main():
    """Main interactive loop."""
    print_banner()
    
    # Initialize LLM
    print("[Init] Initializing LLM...")
    try:
        llm = get_gemini_model()
        print("[Init] LLM initialized successfully.\n")
    except Exception as e:
        print(f"[Error] Failed to initialize LLM: {str(e)}")
        print("[Error] Make sure GOOGLE_API_KEY is set in your .env file.")
        sys.exit(1)
    
    # Initialize checkpointer
    print("[Init] Initializing checkpointer...")
    checkpointer = MemorySaver()
    print("[Init] Checkpointer initialized.\n")
    
    # Initialize agent
    print("[Init] Initializing TutorAgent...")
    try:
        agent = TutorAgent(
            llm=llm,
            checkpointer=checkpointer,
            language="de"
        )
        print("[Init] TutorAgent initialized successfully.\n")
    except Exception as e:
        print(f"[Error] Failed to initialize TutorAgent: {str(e)}")
        sys.exit(1)
    
    # Default state values (can be changed via commands)
    material_id = "test-material-id"
    user_id = "test-user-id"
    current_page = 1
    thread_id = f"{material_id}_{user_id}"
    
    print_state_info(material_id, user_id, current_page, thread_id)
    
    # Interactive loop
    print("Enter your message (or a command starting with !):")
    print("Type '!quit' to exit.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith("!"):
                parts = user_input.split(None, 1)
                command = parts[0].lower()
                
                if command == "!quit":
                    print("\n[Info] Goodbye!\n")
                    break
                
                elif command == "!page":
                    if len(parts) < 2:
                        print("[Error] Usage: !page <number>\n")
                        continue
                    try:
                        current_page = int(parts[1])
                        thread_id = f"{material_id}_{user_id}"
                        print(f"[Info] Current page set to {current_page}\n")
                        print_state_info(material_id, user_id, current_page, thread_id)
                    except ValueError:
                        print(f"[Error] Invalid page number: {parts[1]}\n")
                    continue
                
                elif command == "!material":
                    if len(parts) < 2:
                        print("[Error] Usage: !material <id>\n")
                        continue
                    material_id = parts[1]
                    thread_id = f"{material_id}_{user_id}"
                    print(f"[Info] Material ID set to {material_id}\n")
                    print_state_info(material_id, user_id, current_page, thread_id)
                    continue
                
                elif command == "!user":
                    if len(parts) < 2:
                        print("[Error] Usage: !user <id>\n")
                        continue
                    user_id = parts[1]
                    thread_id = f"{material_id}_{user_id}"
                    print(f"[Info] User ID set to {user_id}\n")
                    print_state_info(material_id, user_id, current_page, thread_id)
                    continue
                
                elif command == "!history":
                    show_history(agent, thread_id)
                    continue
                
                elif command == "!clear":
                    # Reset thread by using a new thread_id with timestamp
                    import time
                    thread_id = f"{material_id}_{user_id}_cleared_{int(time.time())}"
                    print("[Info] Conversation cleared. Starting new thread.\n")
                    print_state_info(material_id, user_id, current_page, thread_id)
                    continue
                
                elif command == "!help":
                    print_banner()
                    continue
                
                else:
                    print(f"[Error] Unknown command: {command}")
                    print("[Info] Type '!help' to see available commands.\n")
                    continue
            
            # Process user message
            print("\n[Agent] Processing your message...\n")
            try:
                response = run_agent(
                    agent=agent,
                    message=user_input,
                    thread_id=thread_id,
                    material_id=material_id,
                    user_id=user_id,
                    current_page=current_page
                )
                
                if response:
                    print("─" * 60)
                    print(f"Agent: {response}")
                    print("─" * 60 + "\n")
                else:
                    print("[Warning] Agent returned empty response.\n")
                
            except Exception as e:
                print(f"[Error] Failed to get agent response: {str(e)}\n")
                import traceback
                if "--debug" in sys.argv:
                    print("\n[Debug] Full traceback:")
                    traceback.print_exc()
                    print()
        
        except KeyboardInterrupt:
            print("\n\n[Info] Interrupted by user. Goodbye!\n")
            break
        except EOFError:
            print("\n\n[Info] Goodbye!\n")
            break
        except Exception as e:
            print(f"\n[Error] Unexpected error: {str(e)}\n")
            if "--debug" in sys.argv:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
