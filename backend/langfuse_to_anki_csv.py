"""
Script zum Konvertieren von Langfuse Trace-Exports direkt in Anki-kompatible CSV

Dieses Script liest eine Langfuse Trace-Export JSON-Datei und extrahiert alle
Flashcards aus den Model-Outputs, um sie direkt in Anki importieren zu können.

Usage:
    python langfuse_to_anki_csv.py --input <langfuse_export.json> --output flashcards.csv
"""

import json
import csv
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional


def extract_json_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """
    Extrahiert JSON aus einem Markdown-Code-Block.
    
    Args:
        text: Text der möglicherweise JSON in ```json ... ``` Blöcken enthält
    
    Returns:
        Parsed JSON als Dict oder None
    """
    # Suche nach JSON-Code-Blöcken
    json_pattern = r'```json\s*\n(.*?)\n```'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Versuche direkt als JSON zu parsen
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Versuche JSON nach dem ersten { zu finden
    start_idx = text.find('{')
    if start_idx != -1:
        # Finde das letzte }
        end_idx = text.rfind('}')
        if end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
    
    return None


def extract_cards_from_output(output: Any) -> List[Dict[str, Any]]:
    """
    Extrahiert Flashcard-Objekte aus einem Output.
    
    Args:
        output: Output-Objekt (kann String, Dict oder List sein)
    
    Returns:
        Liste von Flashcard-Dicts mit 'front', 'back', 'tags'
    """
    cards = []
    
    if isinstance(output, str):
        # Versuche JSON aus String zu extrahieren
        parsed = extract_json_from_markdown(output)
        if parsed:
            if isinstance(parsed, dict) and 'cards' in parsed:
                cards = parsed['cards']
            elif isinstance(parsed, list):
                cards = parsed
    
    elif isinstance(output, dict):
        # Direktes Dict
        if 'cards' in output:
            cards = output['cards']
        elif 'front' in output and 'back' in output:
            # Einzelne Card
            cards = [output]
    
    elif isinstance(output, list):
        # Liste von Cards
        cards = output
    
    # Validiere und normalisiere Cards
    normalized_cards = []
    for card in cards:
        if isinstance(card, dict):
            front = card.get('front', '')
            back = card.get('back', '')
            tags = card.get('tags', [])
            
            # Nur Cards mit Front und Back hinzufügen
            if front and back:
                normalized_cards.append({
                    'front': str(front),
                    'back': str(back),
                    'tags': tags if isinstance(tags, list) else [tags] if tags else []
                })
    
    return normalized_cards


def process_langfuse_export(file_path: Path) -> List[Dict[str, Any]]:
    """
    Verarbeitet eine Langfuse Trace-Export JSON-Datei.
    
    Args:
        file_path: Pfad zur JSON-Datei
    
    Returns:
        Liste aller extrahierten Flashcards
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_cards = []
    
    # Die Datei sollte eine Liste von Traces sein
    if not isinstance(data, list):
        print(f"WARNING: Erwartete Liste, bekam {type(data)}")
        return all_cards
    
    print(f"Verarbeite {len(data)} Traces...")
    
    for idx, trace in enumerate(data, 1):
        trace_id = trace.get('id', f'trace_{idx}')
        output = trace.get('output')
        
        if not output:
            print(f"  Trace {idx}: Kein Output gefunden")
            continue
        
        # Extrahiere Cards aus dem Output
        cards = extract_cards_from_output(output)
        
        if cards:
            print(f"  Trace {idx}: {len(cards)} Cards gefunden")
            all_cards.extend(cards)
        else:
            print(f"  Trace {idx}: Keine Cards im Output gefunden")
    
    return all_cards


def create_anki_csv(cards: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Erstellt eine Anki-kompatible CSV-Datei.
    
    Anki Basic card format:
    - front: Front side of the card
    - back: Back side of the card
    - tags: Space-separated tags
    
    Args:
        cards: Liste von Flashcard-Dicts
        output_path: Pfad zur Ausgabe-CSV-Datei
    """
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        # Anki verwendet Pipe-Delimiter
        writer = csv.writer(f, delimiter='|', quoting=csv.QUOTE_MINIMAL, escapechar='\\')
        
        # Header (Anki ignoriert diesen, aber hilfreich für Debugging)
        writer.writerow(['front', 'back', 'tags'])
        
        # Schreibe Cards
        for card in cards:
            front = card.get('front', '')
            back = card.get('back', '')
            tags = card.get('tags', [])
            
            # Konvertiere Tags-Liste zu String
            if isinstance(tags, list):
                tags_str = ' '.join(str(tag) for tag in tags if tag)
            else:
                tags_str = str(tags) if tags else ''
            
            writer.writerow([front, back, tags_str])
    
    print(f"\nCSV-Datei erstellt: {output_path}")
    print(f"Anzahl Cards: {len(cards)}")


def main():
    parser = argparse.ArgumentParser(
        description='Konvertiere Langfuse Trace-Export zu Anki CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiel:
  python langfuse_to_anki_csv.py --input langfuse_export.json --output flashcards.csv

Die CSV-Datei kann direkt in Anki importiert werden:
  1. Öffne Anki
  2. File → Import
  3. Wähle die CSV-Datei
  4. Stelle sicher, dass "Fields separated by: Pipe (|)" ausgewählt ist
  5. Klicke Import
        """
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Pfad zur Langfuse Trace-Export JSON-Datei'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='flashcards_anki.csv',
        help='Ausgabe-CSV-Datei (Standard: flashcards_anki.csv)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Zeige detaillierte Ausgabe'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Eingabe-Datei nicht gefunden: {input_path}")
        sys.exit(1)
    
    print(f"Lade Langfuse Export: {input_path}")
    
    try:
        cards = process_langfuse_export(input_path)
    except Exception as e:
        print(f"ERROR: Fehler beim Verarbeiten der Datei: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not cards:
        print("WARNING: Keine Cards gefunden!")
        sys.exit(1)
    
    output_path = Path(args.output)
    create_anki_csv(cards, output_path)
    
    # Zeige Zusammenfassung
    print(f"\n=== ZUSAMMENFASSUNG ===")
    print(f"Gesamtanzahl Cards: {len(cards)}")
    
    # Zeige Beispiel-Card
    if args.verbose and cards:
        print(f"\n=== BEISPIEL-CARD ===")
        example = cards[0]
        print(f"Front: {example['front'][:100]}...")
        print(f"Back: {example['back'][:100]}...")
        print(f"Tags: {example['tags']}")
    
    print(f"\nDie CSV-Datei kann jetzt in Anki importiert werden!")
    print(f"Wichtig: Stelle sicher, dass 'Fields separated by: Pipe (|)' in Anki ausgewählt ist.")


if __name__ == "__main__":
    main()
