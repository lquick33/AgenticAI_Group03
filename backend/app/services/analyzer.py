"""
Multimodal Slide Analysis Service

Analyzes lecture slide images using Google Gemini vision model.
Extracted and adapted from PoC to work with in-memory image bytes.
"""

import base64
import io
from typing import Optional

from PIL import Image
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.models.schemas import SlideAnalysis


def get_gemini_model(api_key: Optional[str] = None) -> ChatGoogleGenerativeAI:
    """
    Initialize ChatGoogleGenerativeAI with model selection logic.
    
    Tries gemini-2.5-flash first, falls back to gemini-1.5-flash if unavailable.
    
    Args:
        api_key: Google API key for authentication (uses settings if None)
        
    Returns:
        Configured ChatGoogleGenerativeAI instance
        
    Raises:
        ValueError: If API key is missing or model initialization fails
    """
    if api_key is None:
        api_key = settings.GOOGLE_API_KEY
    
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
            return llm
        except Exception as e:
            if model_name == models_to_try[-1]:
                # Last model failed, raise error
                raise ValueError(
                    f"Failed to initialize Gemini model. Tried: {', '.join(models_to_try)}. "
                    f"Error: {str(e)}"
                )
            # Try next model
            continue
    
    # Should not reach here, but just in case
    raise ValueError("No Gemini model could be initialized")


def image_bytes_to_base64(image_bytes: bytes, format: str = "jpeg") -> str:
    """
    Convert image bytes to base64 data URI format.
    
    Args:
        image_bytes: Raw image bytes
        format: Image format (jpeg, png, etc.)
        
    Returns:
        Base64-encoded data URI string in format: data:image/{format};base64,{base64_string}
        
    Raises:
        ValueError: If image format is not supported or processing fails
    """
    try:
        # Validate image by opening it
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Get actual format from image
            img_format = img.format or format
            img_format_lower = img_format.lower()
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if img_format_lower in ("jpeg", "jpg") and img.mode != "RGB":
                # Convert image to RGB
                rgb_img = img.convert("RGB")
                # Save to bytes
                output = io.BytesIO()
                rgb_img.save(output, format="JPEG")
                image_bytes = output.getvalue()
                img_format_lower = "jpeg"
        
        # Encode to base64
        base64_string = base64.b64encode(image_bytes).decode("utf-8")
        
        # Return as data URI
        return f"data:image/{img_format_lower};base64,{base64_string}"
    
    except Exception as e:
        raise ValueError(f"Failed to process image bytes: {str(e)}")


def analyze_pdf_page(image_bytes: bytes, api_key: Optional[str] = None) -> SlideAnalysis:
    """
    Analyze a PDF page image using Google Gemini vision model.
    
    This function accepts image bytes (from pdf2image conversion) and returns
    structured analysis results. Designed to be used in async contexts and
    can be extracted into LangGraph node functions.
    
    Args:
        image_bytes: Image bytes (typically from PIL Image converted to bytes)
        api_key: Optional Google API key (uses settings if None)
        
    Returns:
        SlideAnalysis Pydantic model with structured analysis results
        
    Raises:
        ValueError: If API key is missing or analysis fails
    """
    # Load API key if not provided
    if api_key is None:
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")
    
    # Convert image bytes to base64 data URI
    image_data_uri = image_bytes_to_base64(image_bytes)
    
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
