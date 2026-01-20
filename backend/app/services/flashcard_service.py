"""
Flashcard Service

Service functions for flashcard operations, including CSV export.
"""

import csv
import io
from typing import List, Dict, Any


def build_anki_csv(cards: List[Dict[str, Any]]) -> bytes:
    """
    Build Anki-compatible CSV file from flashcards.
    
    Anki Basic card format requires 3 columns:
    - front: Front side of the card
    - back: Back side of the card
    - tags: Space-separated tags
    
    Args:
        cards: List of flashcard dicts with keys: front, back, tags
        
    Returns:
        CSV file as bytes (UTF-8 encoded)
    """
    output = io.StringIO()
    
    # Create CSV writer
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, escapechar='\\')
    
    # Write header (Anki doesn't require headers, but it's helpful for debugging)
    # Note: Anki will ignore the header row if present
    writer.writerow(["front", "back", "tags"])
    
    # Write cards
    for card in cards:
        front = card.get("front", "")
        back = card.get("back", "")
        tags = card.get("tags", [])
        
        # Convert tags list to space-separated string
        if isinstance(tags, list):
            tags_str = " ".join(str(tag) for tag in tags)
        else:
            tags_str = str(tags) if tags else ""
        
        # Escape newlines and ensure proper CSV formatting
        # CSV writer handles escaping automatically, but we need to handle newlines
        # Replace newlines with spaces or keep them (Anki supports newlines in fields)
        writer.writerow([front, back, tags_str])
    
    # Get string content and encode to UTF-8 bytes
    csv_string = output.getvalue()
    output.close()
    
    # Add BOM for Excel compatibility (optional, but helpful)
    # UTF-8 BOM: b'\xef\xbb\xbf'
    return csv_string.encode('utf-8-sig')  # utf-8-sig adds BOM automatically
