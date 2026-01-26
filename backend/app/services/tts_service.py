"""
Text-to-Speech Service

Service for generating audio files from text using Google Cloud Text-to-Speech API.
Supports multiple languages through Google Cloud TTS.
"""

import logging
import os
from typing import Optional, Dict
from google.cloud import texttospeech
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global TTS client (singleton)
_tts_client: Optional[texttospeech.TextToSpeechClient] = None


def get_tts_client() -> Optional[texttospeech.TextToSpeechClient]:
    """
    Get or create Google Cloud TTS client instance.
    
    Returns:
        Configured TTS client, or None if credentials are not available
    """
    global _tts_client
    
    if _tts_client is not None:
        return _tts_client
    
    # Check if credentials are configured
    # TTS can work with service account file or default credentials (from environment)
    # Check both settings and environment variable (standard Google Cloud pattern)
    credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    try:
        # Try to use service account credentials if provided
        if credentials_path:
            if os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                _tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
                logger.info(f"Google Cloud TTS client initialized with service account credentials from: {credentials_path}")
                return _tts_client
            else:
                logger.warning(f"Service account credentials file not found: {credentials_path}")
        else:
            # Try to use default credentials from environment (e.g., gcloud auth)
            logger.debug("No explicit service account path configured, trying default credentials")
        
        # Fallback: use default credentials (e.g., from environment or gcloud)
        _tts_client = texttospeech.TextToSpeechClient()
        logger.info("Google Cloud TTS client initialized with default credentials")
        return _tts_client
    
    except Exception as e:
        logger.error(f"Failed to initialize Google Cloud TTS client: {str(e)}", exc_info=True)
        return None


def generate_audio(
    text: str,
    voice_name: Optional[str] = None,
    language_code: Optional[str] = None,
    speaking_rate: Optional[float] = None
) -> Optional[bytes]:
    """
    Generate audio file from text using Google Cloud TTS.
    
    Supports any language supported by Google Cloud Text-to-Speech API.
    Language is determined by the language_code parameter (e.g., "en-US", "zh-CN", "es-ES", "fr-FR").
    
    Args:
        text: Text to convert to speech (any language)
        voice_name: Voice name (default: from settings, or Google's default for language)
        language_code: Language code (default: from settings, typically "zh-CN")
        speaking_rate: Speaking rate (default: 1.0 from settings, range: 0.25 to 4.0)
        
    Returns:
        Audio file bytes (MP3 format), or None if generation fails
    """
    client = get_tts_client()
    if client is None:
        logger.error("TTS client not available. Cannot generate audio.")
        return None
    
    if not text or not text.strip():
        logger.warning("Empty text provided for TTS generation")
        return None
    
    try:
        # Use settings defaults if not provided
        voice_name = voice_name or settings.TTS_VOICE_NAME
        language_code = language_code or settings.TTS_LANGUAGE_CODE
        speaking_rate = speaking_rate or settings.TTS_SPEAKING_RATE
        
        # Configure the voice
        # If voice_name is provided, use it; otherwise let Google choose based on language_code
        if voice_name:
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )
        else:
            # Let Google choose the default voice for the language
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code
            )
        
        # Configure audio encoding
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate
        )
        
        # Synthesize speech
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        logger.debug(f"Generating TTS audio for text: {text[:50]}... (language: {language_code}, voice: {voice_name or 'default'})")
        
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
        except Exception as voice_error:
            # If specific voice fails, try without voice name (let Google choose)
            if voice_name and "does not exist" in str(voice_error):
                logger.warning(f"Voice '{voice_name}' not available, using default voice for {language_code}")
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code
                )
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            else:
                raise
        
        audio_bytes = response.audio_content
        logger.info(f"Successfully generated TTS audio ({len(audio_bytes)} bytes)")
        
        return audio_bytes
    
    except Exception as e:
        logger.error(f"Failed to generate TTS audio: {str(e)}", exc_info=True)
        return None


# Backward compatibility alias
generate_chinese_audio = generate_audio


def contains_chinese(text: str) -> bool:
    """
    Check if text contains Chinese characters.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains Chinese characters (Unicode range U+4E00 to U+9FFF)
    """
    import re
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))


def generate_flashcard_audio(
    character: str,
    sentence: str,
    user_id: str,
    card_id: str
) -> Dict[str, Optional[bytes]]:
    """
    Generate audio files for both character and sentence in a flashcard.
    
    Args:
        character: Chinese character(s) to generate audio for
        sentence: Chinese sentence to generate audio for
        user_id: User ID (for logging/organization)
        card_id: Card ID (for logging/organization)
        
    Returns:
        Dictionary with 'character_audio' and 'sentence_audio' keys containing audio bytes,
        or None values if generation fails
    """
    result = {
        "character_audio": None,
        "sentence_audio": None
    }
    
    # Generate character audio
    if character and contains_chinese(character):
        logger.info(f"Generating character audio for card {card_id}: {character}")
        result["character_audio"] = generate_audio(character)
    else:
        logger.debug(f"Skipping character audio (no Chinese text): {character}")
    
    # Generate sentence audio
    if sentence and contains_chinese(sentence):
        logger.info(f"Generating sentence audio for card {card_id}: {sentence[:50]}...")
        result["sentence_audio"] = generate_audio(sentence)
    else:
        logger.debug(f"Skipping sentence audio (no Chinese text): {sentence[:50] if sentence else 'empty'}...")
    
    return result
