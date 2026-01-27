"""
Tool for text-to-speech conversion.

This tool converts text to audio files using Google Cloud TTS.
Supports multiple languages through the language_code parameter.
Can be used by agents or called directly for audio generation.
"""

import json
import logging
from typing import Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.tts_service import generate_audio

logger = logging.getLogger(__name__)


class TextToSpeechInput(BaseModel):
    """Input schema for the TextToSpeech tool."""
    text: str = Field(..., description="Text to convert to speech (supports any language)")
    voice_name: Optional[str] = Field(
        None,
        description="Optional voice name (e.g., 'en-US-Wavenet-D', 'zh-CN-Wavenet-C', 'es-ES-Wavenet-B'). Leave empty to use default voice for the language."
    )
    language_code: Optional[str] = Field(
        None,
        description="Optional language code (e.g., 'en-US', 'zh-CN', 'es-ES', 'fr-FR', 'de-DE'). Default: from settings (typically 'zh-CN')."
    )
    speaking_rate: Optional[float] = Field(
        None,
        ge=0.25,
        le=4.0,
        description="Optional speaking rate (0.25 to 4.0, default: 1.0). Leave empty to use default."
    )


class TextToSpeechTool:
    """
    Tool for converting text to speech using Google Cloud TTS.
    
    This tool can be used by agents to generate audio files from text in any language
    supported by Google Cloud Text-to-Speech API. Useful for language learning,
    accessibility, and any application requiring text-to-speech conversion.
    """
    
    def __init__(self):
        """Initialize TextToSpeechTool."""
        self.name = "text_to_speech"
        self.description = (
            "Konvertiert Text in Audio-Dateien (Text-to-Speech) mit Google Cloud TTS. "
            "Unterstützt mehrere Sprachen (z.B. Deutsch, Englisch, Chinesisch, Spanisch, Französisch). "
            "Gibt Audio-Daten als Base64-kodierte MP3-Datei zurück. "
            "Parameter: text (der zu konvertierende Text in beliebiger Sprache), "
            "voice_name (optional, z.B. 'de-DE-Wavenet-B', 'en-US-Wavenet-D', 'zh-CN-Wavenet-C'), "
            "language_code (optional, z.B. 'de-DE', 'en-US', 'zh-CN', 'es-ES', Standard: aus Einstellungen), "
            "speaking_rate (optional, 0.25-4.0, Standard: 1.0)."
        )
    
    def _run(
        self,
        text: str,
        voice_name: Optional[str] = None,
        language_code: Optional[str] = None,
        speaking_rate: Optional[float] = None
    ) -> str:
        """
        Execute the tool synchronously.
        
        Args:
            text: Text to convert to speech
            voice_name: Optional voice name
            language_code: Optional language code
            speaking_rate: Optional speaking rate (0.25 to 4.0)
            
        Returns:
            JSON string with audio data (base64 encoded) or error message
        """
        try:
            # Validate input
            if not text or not text.strip():
                error_response = {
                    "error": "Text cannot be empty",
                    "error_type": "ValidationError",
                    "audio_base64": None
                }
                return json.dumps(error_response, ensure_ascii=False)
            
            # Generate audio
            logger.info(f"Generating TTS audio for text: {text[:50]}... (language: {language_code or 'default'})")
            audio_bytes = generate_audio(
                text=text,
                voice_name=voice_name,
                language_code=language_code,
                speaking_rate=speaking_rate
            )
            
            if audio_bytes is None:
                error_response = {
                    "error": "Failed to generate audio. Check TTS service configuration.",
                    "error_type": "TTSError",
                    "audio_base64": None
                }
                return json.dumps(error_response, ensure_ascii=False)
            
            # Encode audio as base64 for JSON response
            import base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create success response
            success_response = {
                "success": True,
                "audio_base64": audio_base64,
                "audio_size_bytes": len(audio_bytes),
                "text": text[:100],  # Include first 100 chars for reference
                "format": "mp3"
            }
            
            logger.info(f"Successfully generated TTS audio ({len(audio_bytes)} bytes)")
            return json.dumps(success_response, ensure_ascii=False)
        
        except Exception as e:
            # Wrap unexpected errors and return as JSON string
            logger.error(f"Unexpected error in text_to_speech: {str(e)}", exc_info=True)
            error_response = {
                "error": f"Fehler bei Text-to-Speech-Konvertierung: {str(e)}",
                "error_type": type(e).__name__,
                "audio_base64": None,
                "details": {"error_type": type(e).__name__, "error_message": str(e)}
            }
            return json.dumps(error_response, ensure_ascii=False)
    
    async def _arun(
        self,
        text: str,
        voice_name: Optional[str] = None,
        language_code: Optional[str] = None,
        speaking_rate: Optional[float] = None
    ) -> str:
        """
        Execute the tool asynchronously.
        
        Args:
            text: Text to convert to speech
            voice_name: Optional voice name
            language_code: Optional language code
            speaking_rate: Optional speaking rate
            
        Returns:
            JSON string with audio data or error message
        """
        # For now, use sync implementation
        # TTS service is sync, so we can call it directly
        return self._run(text, voice_name, language_code, speaking_rate)
    
    def to_langchain_tool(self) -> StructuredTool:
        """
        Convert this tool to a LangChain StructuredTool.
        
        Returns:
            LangChain StructuredTool instance
        """
        return StructuredTool(
            name=self.name,
            description=self.description,
            func=self._run,
            args_schema=TextToSpeechInput
        )
