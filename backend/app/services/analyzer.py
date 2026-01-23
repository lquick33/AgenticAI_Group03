"""
Multimodal Slide Analysis Service

Analyzes lecture slide images using Google Gemini vision model.
Extracted and adapted from PoC to work with in-memory image bytes.
"""

import base64
import io
import json
from typing import Optional, Sequence

from PIL import Image
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.models.schemas import SlideAnalysis
from app.services.observability import create_callback_handler
import logging

logger = logging.getLogger(__name__)


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


async def analyze_pdf_page(
    image_bytes: bytes, 
    api_key: Optional[str] = None,
    material_id: Optional[str] = None,
    user_id: Optional[str] = None,
    page_number: Optional[int] = None
) -> SlideAnalysis:
    """
    Analyze a PDF page image using Google Gemini vision model (async).
    
    This function accepts image bytes (from pdf2image conversion) and returns
    structured analysis results. Designed to be used in async contexts and
    can be extracted into LangGraph node functions.
    
    Args:
        image_bytes: Image bytes (typically from PIL Image converted to bytes)
        api_key: Optional Google API key (uses settings if None)
        material_id: Course material ID for Langfuse tracking (optional)
        user_id: User ID for Langfuse tracking (optional)
        page_number: Page number for Langfuse tracking (optional)
        
    Returns:
        SlideAnalysis Pydantic model with structured analysis results
        
    Raises:
        ValueError: If API key is missing or analysis fails
    """
    import asyncio
    
    # Load API key if not provided
    if api_key is None:
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")
    
    # Convert image bytes to base64 data URI
    image_data_uri = image_bytes_to_base64(image_bytes)
    
    # Initialize LLM with structured output
    llm = get_gemini_model(api_key)
    structured_llm = llm.with_structured_output(SlideAnalysis).with_config({"run_name": "pdf-llm-page-analysis"})
    
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
    
    # Create Langfuse callback handler für automatisches Tracking
    callback_handler = create_callback_handler()
    
    # Prepare config with callbacks and metadata
    config = {}
    if callback_handler:
        metadata = {
            "langfuse_user_id": user_id,
            "langfuse_session_id": material_id,  # Use material_id as session
            "material_id": material_id,
            "page_number": page_number,
            "agent_name": "PDFAnalyzer",
            "operation": "page_analysis"
        }
        config["callbacks"] = [callback_handler]
        config["metadata"] = metadata
        logger.debug(f"🟡 Langfuse: Sending page_analysis LLM call with metadata: user_id={user_id}, material_id={material_id}, page={page_number}")
    
    # Invoke LLM and get structured output (run in thread pool since LangChain is sync)
    try:
        # Run synchronous invoke in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: structured_llm.invoke([message], config=config if config else None)
        )
        
        if callback_handler:
            logger.debug("🟢 Langfuse: Page analysis LLM call completed - data tracked by CallbackHandler")
        
        return result
    except Exception as e:
        raise ValueError(f"Failed to analyze slide: {str(e)}")


async def generate_material_summary(
    page_data: Sequence[dict],
    api_key: Optional[str] = None,
    material_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> str:
    """
    Generate a global topics summary for a lecture from per-page analyses.

    The function expects a list of dicts with the keys:
    - page_number: int
    - summary: str
    - key_terms: list[str]
    - exam_questions: list[str] (optional)

    It returns a JSON string with the following (informal) schema:
    {
      "overall_summary": str,
      "main_topics": [
        {
          "name": str,
          "description": str,
          "related_pages": int[],
          "key_terms": str[]
        },
        ...
      ]
    }

    The JSON is intentionally stored as TEXT in the database so that
    downstream agents (Meta-Agent, Tutor-Agent) can parse and extend it
    flexibly over time.
    """
    import asyncio

    if not page_data:
        # Empty JSON structure as safe fallback
        empty_summary = {
            "overall_summary": "",
            "main_topics": [],
        }
        return json.dumps(empty_summary, ensure_ascii=False)

    # Load API key if not provided
    if api_key is None:
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")

    llm = get_gemini_model(api_key).with_config({"run_name": "pdf-llm-material-summary"})

    # We call the base Chat model (no structured_output), but enforce
    # JSON-only output via the prompt.
    # To keep token usage in check, we truncate very long summaries.
    MAX_SUMMARY_CHARS = 400
    MAX_PAGES_FOR_CONTEXT = 120  # hard cap for very long PDFs

    trimmed_pages = []
    for entry in list(page_data)[:MAX_PAGES_FOR_CONTEXT]:
        page_number = entry.get("page_number")
        summary = entry.get("summary") or ""
        key_terms = entry.get("key_terms") or []
        exam_questions = entry.get("exam_questions") or []

        if len(summary) > MAX_SUMMARY_CHARS:
            summary = summary[:MAX_SUMMARY_CHARS] + " …"

        trimmed_pages.append(
            {
                "page_number": page_number,
                "summary": summary,
                "key_terms": key_terms,
                "exam_questions": exam_questions,
            }
        )

    pages_json = json.dumps(trimmed_pages, ensure_ascii=False)

    system_instructions = (
        "Du bist ein Assistent, der aus Vorlesungsfolien eine strukturierte Themenübersicht "
        "für ein gesamtes Skript/Modul erstellt. "
        "Du bekommst pro Folie eine kurze Zusammenfassung und Key Terms. "
    )

    user_prompt = f"""
Analysiere die folgenden Seiten einer Vorlesung und erstelle eine globale Themenübersicht.

Du bekommst eine JSON-Liste `pages` mit Einträgen:
- page_number: Seitennummer (int)
- summary: kurze Zusammenfassung der Seite (string)
- key_terms: wichtige Begriffe (string[])
- exam_questions: optionale Prüfungsfragen (string[])

Deine Aufgabe:
1. Fasse die gesamte Vorlesung in einem prägnanten Überblickstext zusammen.
2. Identifiziere die wichtigsten Kernthemen/Konzepte (3–15 Stück, je nach Inhalt).
3. Ordne zu jedem Thema die relevanten Seitennummern und zentralen Fachbegriffe zu.

Gib **ausschließlich** ein gültiges JSON-Objekt mit folgendem Schema zurück:
{{
  "overall_summary": string,    // 3–5 Sätze auf Deutsch, Überblick über die Vorlesung
  "main_topics": [
    {{
      "name": string,           // kurzer Themenname, z.B. "Lineare Regression"
      "description": string,    // 1–3 Sätze, was in diesem Thema behandelt wird
      "related_pages": number[],// Liste von Seitennummern, auf denen dieses Thema vorkommt
      "key_terms": string[]     // wichtigste Begriffe zu diesem Thema
    }}
  ]
}}

WICHTIG:
- Antworte **nur** mit JSON, ohne zusätzlichen Erklärungstext.
- Falls die Inhalte sehr einseitig sind, kannst du auch weniger Themen wählen.

Hier sind die Seitendaten:

pages = {pages_json}
"""

    message = HumanMessage(content=[{"type": "text", "text": system_instructions + "\n\n" + user_prompt}])

    # Create Langfuse callback handler für automatisches Tracking
    callback_handler = create_callback_handler()
    
    # Prepare config with callbacks and metadata
    config = {}
    if callback_handler:
        metadata = {
            "langfuse_user_id": user_id,
            "langfuse_session_id": material_id,  # Use material_id as session
            "material_id": material_id,
            "agent_name": "PDFAnalyzer",
            "operation": "material_summary"
        }
        config["callbacks"] = [callback_handler]
        config["metadata"] = metadata
        logger.debug(f"🟡 Langfuse: Sending material_summary LLM call with metadata: user_id={user_id}, material_id={material_id}")
    
    try:
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(
            None, 
            lambda: llm.invoke([message], config=config if config else None)
        )
        
        if callback_handler:
            logger.debug("🟢 Langfuse: Material summary LLM call completed - data tracked by CallbackHandler")

        text = getattr(raw_response, "content", None)
        if not isinstance(text, str):
            # Some LangChain wrappers return a list; fall back sensibly
            if isinstance(text, list) and text and isinstance(text[0], str):
                text = text[0]
            else:
                # As a last resort, dump the whole object
                text = str(raw_response)

        # Try to validate JSON; if it fails, wrap it into minimal schema
        try:
            parsed = json.loads(text)
            # Basic sanity check
            if not isinstance(parsed, dict) or "overall_summary" not in parsed:
                raise ValueError("JSON schema missing required keys")
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            fallback = {
                "overall_summary": text,
                "main_topics": [],
            }
            return json.dumps(fallback, ensure_ascii=False)
    except Exception as e:
        # In case of LLM failure, return empty structure so pipeline can continue
        empty_summary = {
            "overall_summary": "",
            "main_topics": [],
            "error": f"Failed to generate material summary: {str(e)}",
        }
        return json.dumps(empty_summary, ensure_ascii=False)


async def generate_material_filename(
    page_one_summary: str,
    api_key: Optional[str] = None,
    material_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> str:
    """
    Generate a professional filename for a course material based on the summary of page 1.
    
    This function takes the summary from the first page of a lecture and generates
    a clean, descriptive filename that replaces unprofessional names like
    "00_AlgebraGrundwissen (1).pdf" with something like "Kapitel 0: Algebra-Grundwissen".
    
    Args:
        page_one_summary: The summary text from page 1 analysis
        api_key: Optional Google API key (uses settings if None)
        material_id: Course material ID for Langfuse tracking (optional)
        user_id: User ID for Langfuse tracking (optional)
        
    Returns:
        A clean, professional filename (without file extension)
        
    Raises:
        ValueError: If API key is missing or generation fails
    """
    import asyncio
    
    # Load API key if not provided
    if api_key is None:
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")
    
    if not page_one_summary or not page_one_summary.strip():
        # Fallback if no summary available
        return "Vorlesungsmaterial"
    
    llm = get_gemini_model(api_key).with_config({"run_name": "pdf-llm-filename-generation"})
    
    system_instructions = (
        "Du bist ein Assistent, der aus einer Zusammenfassung der ersten Seite einer Vorlesung "
        "einen professionellen, aussagekräftigen Dateinamen generiert. "
        "Der Dateiname soll das Thema/Kapitel der Vorlesung klar beschreiben."
    )
    
    user_prompt = f"""
Basierend auf der folgenden Zusammenfassung der ersten Seite einer Vorlesung, erstelle einen professionellen Dateinamen.

Zusammenfassung der ersten Seite:
{page_one_summary}

Anforderungen an den Dateinamen:
- Soll das Hauptthema oder Kapitel der Vorlesung widerspiegeln
- Format: "Kapitel X: Thema" oder ähnlich, falls ein Kapitel erkennbar ist
- Falls kein Kapitel erkennbar: nur das Thema
- Professionell und aussagekräftig
- Keine Dateiendung (.pdf) anfügen
- Keine Sonderzeichen wie Klammern, Unterstriche (außer Bindestriche)
- Maximal 100 Zeichen

Beispiele:
- "Kapitel 0: Algebra-Grundwissen"
- "Einführung in die Lineare Algebra"
- "Kapitel 1: Beweisverfahren"

Gib **nur** den Dateinamen zurück, ohne zusätzlichen Text oder Erklärungen.
"""
    
    message = HumanMessage(content=[{"type": "text", "text": system_instructions + "\n\n" + user_prompt}])
    
    # Create Langfuse callback handler für automatisches Tracking
    callback_handler = create_callback_handler()
    
    # Prepare config with callbacks and metadata
    config = {}
    if callback_handler:
        metadata = {
            "langfuse_user_id": user_id,
            "langfuse_session_id": material_id,  # Use material_id as session
            "material_id": material_id,
            "agent_name": "PDFAnalyzer",
            "operation": "filename_generation"
        }
        config["callbacks"] = [callback_handler]
        config["metadata"] = metadata
        logger.debug(f"🟡 Langfuse: Sending filename_generation LLM call with metadata: user_id={user_id}, material_id={material_id}")
    
    try:
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(
            None, 
            lambda: llm.invoke([message], config=config if config else None)
        )
        
        if callback_handler:
            logger.debug("🟢 Langfuse: Filename generation LLM call completed - data tracked by CallbackHandler")
        
        text = getattr(raw_response, "content", None)
        if not isinstance(text, str):
            # Some LangChain wrappers return a list; fall back sensibly
            if isinstance(text, list) and text and isinstance(text[0], str):
                text = text[0]
            else:
                # As a last resort, dump the whole object
                text = str(raw_response)
        
        # Clean up the response - remove quotes, whitespace, and file extensions
        filename = text.strip()
        # Remove surrounding quotes if present
        if filename.startswith('"') and filename.endswith('"'):
            filename = filename[1:-1]
        if filename.startswith("'") and filename.endswith("'"):
            filename = filename[1:-1]
        # Remove file extensions
        filename = filename.replace(".pdf", "").replace(".PDF", "")
        # Limit length
        if len(filename) > 100:
            filename = filename[:100].strip()
        
        # Fallback if result is empty
        if not filename:
            filename = "Vorlesungsmaterial"
        
        logger.info(f"Generated filename: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Failed to generate filename: {str(e)}", exc_info=True)
        # Return fallback filename on error
        return "Vorlesungsmaterial"

