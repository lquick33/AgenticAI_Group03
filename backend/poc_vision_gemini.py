"""
Proof of Concept: Vision-First Slide Analysis with Google Gemini

This script demonstrates analyzing lecture slides using Google Gemini's vision capabilities
with structured output via LangChain. The analysis function is designed to be compatible
with future LangGraph integration as a node function.

Usage:
    python poc_vision_gemini.py [image_path]

Requirements:
    - GOOGLE_API_KEY in .env file
    - test_slide.jpg (or provide image path as argument)
"""

import os
import base64
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from PIL import Image


# Load environment variables
load_dotenv()


class SlideAnalysis(BaseModel):
    """
    Structured analysis result for a lecture slide.
    
    This model defines the expected output structure from the multimodal LLM analysis.
    Used for type-safe structured output with LangChain's with_structured_output().
    
    Future Integration:
        This will be used in LangGraph nodes to process slide images and store
        results in the page_analyses table in Supabase.
    """
    
    summary: str = Field(
        ...,
        description="Eine prägnante Zusammenfassung des Folieninhalts"
    )
    
    key_terms: list[str] = Field(
        ...,
        description="Die wichtigsten Fachbegriffe auf der Folie"
    )
    
    exam_questions: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Genau 2 mögliche Prüfungsfragen, die sich aus dem Inhalt ergeben"
    )
    
    diagram_description: str = Field(
        ...,
        description="Beschreibung visueller Elemente (Diagramme, Charts, Grafiken). Falls nur Text vorhanden, dann 'Kein Diagramm'"
    )


def load_image_as_base64(image_path: str) -> str:
    """
    Load an image file and convert it to base64 data URI format.
    
    Args:
        image_path: Path to the image file (JPG, PNG, etc.)
        
    Returns:
        Base64-encoded data URI string in format: data:image/{format};base64,{base64_string}
        
    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If image format is not supported
    """
    image_file = Path(image_path)
    
    if not image_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Open and validate image
    try:
        with Image.open(image_file) as img:
            # Get image format (JPEG, PNG, etc.)
            img_format = img.format or "jpeg"
            img_format_lower = img_format.lower()
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if img_format_lower in ("jpeg", "jpg") and img.mode != "RGB":
                img = img.convert("RGB")
            
            # Read file as binary and encode to base64
            with open(image_file, "rb") as f:
                image_bytes = f.read()
            
            base64_string = base64.b64encode(image_bytes).decode("utf-8")
            
            # Return as data URI
            return f"data:image/{img_format_lower};base64,{base64_string}"
    
    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}")


def get_gemini_model(api_key: str) -> ChatGoogleGenerativeAI:
    """
    Initialize ChatGoogleGenerativeAI with model selection logic.
    
    Tries gemini-2.0-flash-exp first, falls back to gemini-1.5-flash if unavailable.
    
    Args:
        api_key: Google API key for authentication
        
    Returns:
        Configured ChatGoogleGenerativeAI instance
        
    Raises:
        ValueError: If API key is missing or model initialization fails
    """
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required. Please set it in your .env file.")
    
    # Try newer model first, fallback to stable version
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=0.1  # Lower temperature for more consistent structured output
            )
            # Test if model is accessible by checking if it can be instantiated
            print(f"Using model: {model_name}")
            return llm
        except Exception as e:
            if model_name == models_to_try[-1]:
                # Last model failed, raise error
                raise ValueError(
                    f"Failed to initialize Gemini model. Tried: {', '.join(models_to_try)}. "
                    f"Error: {str(e)}"
                )
            # Try next model
            print(f"Model {model_name} not available, trying fallback...")
            continue
    
    # Should not reach here, but just in case
    raise ValueError("No Gemini model could be initialized")


def analyze_slide(image_path: str, api_key: Optional[str] = None) -> SlideAnalysis:
    """
    Analyze a lecture slide image using Google Gemini vision model.
    
    This function is designed to be extracted and used as a LangGraph node function.
    In LangGraph, it would be called as:
        async def analyze_slide_node(state: AgentState) -> AgentState:
            image_path = state["current_image_path"]
            analysis = analyze_slide(image_path, api_key)
            state["analysis"] = analysis.model_dump()
            return state
    
    Args:
        image_path: Path to the slide image file
        api_key: Optional Google API key (if None, loads from environment)
        
    Returns:
        SlideAnalysis Pydantic model with structured analysis results
        
    Raises:
        FileNotFoundError: If image file doesn't exist
        ValueError: If API key is missing or analysis fails
    """
    # Load API key if not provided
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    # Load and encode image
    image_data_uri = load_image_as_base64(image_path)
    
    # Initialize LLM with structured output
    llm = get_gemini_model(api_key)
    structured_llm = llm.with_structured_output(SlideAnalysis)
    
    # Create prompt for analysis
    analysis_prompt = """Analysiere diese Vorlesungsfolie gründlich und extrahiere strukturierte Informationen.

Gib eine prägnante Zusammenfassung des Inhalts, identifiziere die wichtigsten Fachbegriffe,
formuliere genau 2 mögliche Prüfungsfragen basierend auf dem Inhalt, und beschreibe alle
visuellen Elemente (Diagramme, Charts, Grafiken). Falls keine visuellen Elemente vorhanden sind,
schreibe 'Kein Diagramm' für diagram_description."""
    
    # Create HumanMessage with image
    message = HumanMessage(
        content=[
            {"type": "text", "text": analysis_prompt},
            {"type": "image_url", "image_url": {"url": image_data_uri}}
        ]
    )
    
    # Invoke LLM and get structured output
    try:
        result = structured_llm.invoke([message])
        return result
    except Exception as e:
        raise ValueError(f"Failed to analyze slide: {str(e)}")


def main() -> None:
    """
    Main execution block for the PoC script.
    
    Loads environment, analyzes test image, and prints JSON output.
    """
    # Get image path from command line or use default
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Default to test_slide.jpg in script directory
        script_dir = Path(__file__).parent
        image_path = script_dir / "test_slide.jpg"
    
    # Check if image exists
    if not Path(image_path).exists():
        print(f"Error: Image file not found: {image_path}")
        print(f"Usage: python poc_vision_gemini.py [image_path]")
        print(f"Or place a test_slide.jpg file in the backend/ directory")
        sys.exit(1)
    
    try:
        # Analyze slide
        print(f"Analyzing slide: {image_path}")
        print("=" * 50)
        
        analysis = analyze_slide(str(image_path))
        
        # Print JSON output
        print("\nAnalysis Result (JSON):")
        print("=" * 50)
        print(analysis.model_dump_json(indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 50)
        print("Analysis completed successfully!")
        
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
