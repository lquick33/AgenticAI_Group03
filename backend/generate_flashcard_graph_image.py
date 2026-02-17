"""
Script to generate a visual representation of the Flashcard Generator Agent graph.

This script creates a PNG image of the LangGraph workflow for the FlashcardGeneratorAgent
using the built-in draw_mermaid_png() method with transparent background.
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent))

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from PIL import Image

from app.agents.flashcards.flashcard_agent import FlashcardGeneratorAgent
from app.core.config import settings


def generate_graph_image():
    """Generate PNG image of the Flashcard Generator Agent graph."""
    
    print("[*] Initializing Flashcard Generator Agent...")
    
    # Initialize LLM (required for agent initialization)
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # Use stable model for graph generation
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1
        )
        print("[OK] LLM initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize LLM: {e}")
        print("[INFO] Make sure GOOGLE_API_KEY is set in your .env file")
        return False
    
    # Initialize checkpointer
    checkpointer = MemorySaver()
    
    # Initialize agent
    # FlashcardGeneratorAgent doesn't require a system prompt in __init__
    try:
        agent = FlashcardGeneratorAgent(
            llm=llm,
            checkpointer=checkpointer,
            language="de"
        )
        print("[OK] Flashcard Generator Agent initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Flashcard Generator Agent: {e}")
        print("[INFO] Note: If Langfuse is required, make sure LANGFUSE_* env vars are set")
        import traceback
        traceback.print_exc()
        return False
    
    # Get the compiled graph
    if not agent.graph:
        print("[ERROR] Graph not found. Agent initialization may have failed.")
        return False
    
    print("[*] Generating graph visualization...")
    
    try:
        # Get the graph object
        graph_obj = agent.graph.get_graph()
        
        # Generate PNG image (first to a temporary file)
        temp_path = "flashcard_agent_graph_temp.png"
        output_path = "flashcard_agent_graph.png"
        
        # Try to generate with transparent background parameter (if supported)
        transparent_param_supported = False
        try:
            # Some versions might support background_color parameter
            graph_obj.draw_mermaid_png(output_file_path=temp_path, background_color="transparent")
            print("[INFO] Generated with transparent background parameter")
            transparent_param_supported = True
        except (TypeError, ValueError) as e:
            # If parameter not supported, generate normally and process with PIL
            graph_obj.draw_mermaid_png(output_file_path=temp_path)
            print(f"[INFO] Generated image, processing to make background transparent... (reason: {type(e).__name__})")
        
        if not transparent_param_supported:
            # Make background transparent using PIL
            img = Image.open(temp_path)
            
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Get image data
            data = img.getdata()
            
            # Create new image data with transparent background
            # White pixels (or very light pixels) become transparent
            new_data = []
            for item in data:
                # If pixel is white or very light (threshold: RGB > 240), make it transparent
                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                    # Make transparent
                    new_data.append((255, 255, 255, 0))
                else:
                    # Keep original pixel
                    new_data.append(item)
            
            # Update image with new data
            img.putdata(new_data)
            
            # Save with transparency
            img.save(output_path, 'PNG')
            
            # Remove temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            # If transparent parameter worked, just rename
            if os.path.exists(temp_path):
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_path, output_path)
        
        print(f"[OK] Graph image with transparent background saved to: {output_path}")
        print(f"[INFO] Full path: {os.path.abspath(output_path)}")
        
        # Also print ASCII version for quick preview (optional)
        try:
            print("\n[ASCII Preview]")
            print("-" * 60)
            graph_obj.print_ascii()
            print("-" * 60)
        except ImportError as e:
            print(f"[INFO] ASCII preview skipped: {e}")
        except Exception as e:
            print(f"[INFO] ASCII preview skipped: {type(e).__name__}: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to generate graph image: {e}")
        print(f"[INFO] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Flashcard Generator Agent Graph Visualizer")
    print("=" * 60)
    print()
    
    success = generate_graph_image()
    
    if success:
        print("\n[SUCCESS] Graph generation completed successfully!")
    else:
        print("\n[FAILED] Graph generation failed. Check errors above.")
        sys.exit(1)
