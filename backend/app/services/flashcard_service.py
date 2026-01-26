"""
Flashcard Service

Service functions for flashcard operations, including Anki .apkg export.
"""

import hashlib
import io
import logging
import os
import re
import tempfile
from typing import List, Dict, Any, Tuple, Optional

import genanki

from app.services.snippet_service import download_snippet_image

logger = logging.getLogger(__name__)


# Unique IDs for genanki Model and Deck (generated once, reused)
# These should be consistent so Anki recognizes updates to existing decks
ANKI_MODEL_ID = 1607392319  # Random unique ID for the model
ANKI_DECK_ID = 2081905368   # Random unique ID for the deck


def _create_anki_model() -> genanki.Model:
    """
    Create the Anki note model (card template).
    
    Uses a "Basic with Image" template that shows:
    - Front: Question
    - Back: Answer with optional embedded image
    """
    return genanki.Model(
        ANKI_MODEL_ID,
        'Lernkompanien Basic',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ],
        css='''
.card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
}
img {
    max-width: 100%;
    height: auto;
}
'''
    )


def _extract_image_urls(html: str) -> List[str]:
    """
    Extract image URLs from HTML img tags.
    
    Args:
        html: HTML string containing img tags
        
    Returns:
        List of image URLs found
    """
    # Match both single and double quoted src attributes
    pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    return re.findall(pattern, html, re.IGNORECASE)


def _extract_page_number_from_tags(tags: List[str]) -> Optional[int]:
    """
    Extract page number from tags.
    
    Tags may contain 'page:X' where X is the page number.
    
    Args:
        tags: List of tags
        
    Returns:
        Page number or None if not found
    """
    for tag in tags:
        if tag.startswith("page:"):
            try:
                return int(tag.split(":")[1])
            except (ValueError, IndexError):
                pass
    return None


def _generate_image_filename(url: str, page_number: Optional[int]) -> str:
    """
    Generate a unique filename for an image.
    
    Format: snippet_page_{page_number}_{hash}.png
    
    Args:
        url: Original image URL
        page_number: Page number from tags
        
    Returns:
        Generated filename
    """
    # Create hash from URL for uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    
    if page_number is not None:
        return f"snippet_page_{page_number}_{url_hash}.png"
    else:
        return f"snippet_{url_hash}.png"


def _extract_image_path_from_url(url: str) -> Optional[str]:
    """
    Extract the storage path from a Supabase storage URL.
    
    URLs can be:
    - Public: .../storage/v1/object/public/bucket_name/path
    - Signed: .../storage/v1/object/sign/bucket_name/path?token=...
    
    Args:
        url: Supabase storage URL
        
    Returns:
        Storage path or None if not a valid Supabase URL
    """
    # Match public bucket URL
    public_match = re.search(r'/storage/v1/object/public/[^/]+/(.+)$', url)
    if public_match:
        return public_match.group(1)
    
    # Match signed URL (path is before the ?token=)
    signed_match = re.search(r'/storage/v1/object/sign/[^/]+/([^?]+)', url)
    if signed_match:
        return signed_match.group(1)
    
    return None


def build_anki_apkg(
    cards: List[Dict[str, Any]],
    deck_name: str = "Lernkompanien Flashcards"
) -> bytes:
    """
    Build Anki .apkg package file from flashcards with embedded images.
    
    This function:
    1. Creates a genanki deck with a custom model
    2. For each card, extracts image URLs from the back field
    3. Downloads images from Supabase storage
    4. Replaces URLs with local filenames in the card content
    5. Packages everything into an .apkg file
    
    Args:
        cards: List of flashcard dicts with keys: front, back, tags
        deck_name: Name of the Anki deck
        
    Returns:
        .apkg file as bytes
    """
    logger.info(f"Building Anki .apkg with {len(cards)} cards")
    
    # Create model and deck
    model = _create_anki_model()
    deck = genanki.Deck(ANKI_DECK_ID, deck_name)
    
    # Collect media files: list of (filename, bytes) tuples
    media_files: List[Tuple[str, bytes]] = []
    downloaded_urls: Dict[str, str] = {}  # url -> filename mapping to avoid duplicate downloads
    
    # Process each card
    for card in cards:
        front = card.get("front", "")
        back = card.get("back", "")
        tags = card.get("tags", [])
        
        # Convert tags list to list of strings and sanitize for Anki
        # Anki tags cannot contain spaces - replace with underscores
        if isinstance(tags, list):
            tags_list = [str(tag).replace(" ", "_") for tag in tags]
        else:
            tags_list = [str(tags).replace(" ", "_")] if tags else []
        
        # Extract page number from tags for filename generation
        page_number = _extract_page_number_from_tags(tags_list)
        
        # Extract and process image URLs from back field
        image_urls = _extract_image_urls(back)
        
        # Debug: Log what we found
        if '<img' in back.lower():
            logger.info(f"Card contains <img> tag. Found {len(image_urls)} extractable URLs")
            if not image_urls:
                # Log a snippet of the back to see why extraction failed
                img_start = back.lower().find('<img')
                if img_start != -1:
                    logger.warning(f"⚠️ Could not extract URL from img tag: {back[img_start:img_start+150]}...")
        
        for url in image_urls:
            # Skip if we've already processed this URL
            if url in downloaded_urls:
                # Replace URL with already-downloaded filename
                back = back.replace(url, downloaded_urls[url])
                continue
            
            # Generate unique filename
            filename = _generate_image_filename(url, page_number)
            
            # Try to download the image
            try:
                # Extract storage path from URL
                image_path = _extract_image_path_from_url(url)
                
                if image_path:
                    logger.info(f"Downloading image: {image_path[:50]}...")
                    image_bytes = download_snippet_image(image_path)
                    
                    # Add to media files
                    media_files.append((filename, image_bytes))
                    downloaded_urls[url] = filename
                    
                    # Replace URL with local filename in back field
                    back = back.replace(url, filename)
                    logger.info(f"✅ Replaced URL with local filename: {filename}")
                else:
                    logger.warning(f"⚠️ Could not extract storage path from URL: {url[:80]}...")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to download image, keeping URL: {e}")
                # Keep the original URL if download fails
        
        # Create genanki Note
        note = genanki.Note(
            model=model,
            fields=[front, back],
            tags=tags_list
        )
        deck.add_note(note)
    
    logger.info(f"Created deck with {len(deck.notes)} notes and {len(media_files)} media files")
    
    # Create package with media files
    package = genanki.Package(deck)
    
    # Write media files to temporary directory and add to package
    with tempfile.TemporaryDirectory() as temp_dir:
        media_paths = []
        for filename, file_bytes in media_files:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            media_paths.append(file_path)
        
        package.media_files = media_paths
        
        # Write .apkg to a temporary file, then read bytes
        apkg_path = os.path.join(temp_dir, "output.apkg")
        package.write_to_file(apkg_path)
        
        with open(apkg_path, 'rb') as f:
            apkg_bytes = f.read()
    
    logger.info(f"✅ Generated .apkg file ({len(apkg_bytes)} bytes)")
    return apkg_bytes
