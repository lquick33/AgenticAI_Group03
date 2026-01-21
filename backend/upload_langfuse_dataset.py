"""
Script zum Hochladen des Flashcard Agent Test-Datasets in Langfuse

Dieses Script lädt das Dataset mit komplexen mathematischen Ausdrücken
in Langfuse hoch, damit es für Prompt Testing verwendet werden kann.

Usage:
    python upload_langfuse_dataset.py

Voraussetzungen:
    - LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY müssen in .env gesetzt sein
    - Das Dataset-File flashcard_prompt_test_dataset_langfuse.json muss existieren
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Langfuse import
try:
    from langfuse import Langfuse
except ImportError:
    print("ERROR: Langfuse ist nicht installiert. Bitte installieren Sie es mit: pip install langfuse")
    sys.exit(1)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def load_dataset(file_path: Path) -> Dict[str, Any]:
    """Lädt das Dataset aus der JSON-Datei."""
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset-Datei nicht gefunden: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_langfuse_dataset(
    langfuse_client: Langfuse,
    dataset_name: str,
    description: str = None
) -> str:
    """
    Erstellt ein neues Dataset in Langfuse oder gibt die ID zurück, falls es bereits existiert.
    
    Returns:
        Dataset ID
    """
    try:
        # Versuche, das Dataset zu erstellen
        dataset = langfuse_client.create_dataset(name=dataset_name, description=description)
        print(f"OK: Dataset '{dataset_name}' erstellt")
        return dataset.id
    except Exception as e:
        # Falls das Dataset bereits existiert, versuche es zu finden
        print(f"WARNING: Fehler beim Erstellen (möglicherweise existiert es bereits): {e}")
        # In der aktuellen Langfuse API gibt es keine direkte "get_dataset" Methode
        # Daher geben wir den Namen zurück und der Benutzer muss es manuell prüfen
        print(f"INFO: Bitte prüfen Sie in der Langfuse UI, ob das Dataset '{dataset_name}' bereits existiert")
        return dataset_name


def upload_dataset_items(
    langfuse_client: Langfuse,
    dataset_name: str,
    items: List[Dict[str, Any]]
) -> None:
    """
    Lädt Dataset-Items in Langfuse hoch.
    
    Jedes Item muss folgende Struktur haben:
    {
        "input": {
            "summary": "...",
            "key_terms": [...],
            "exam_questions": [...],
            "diagram_description": "...",
            "conversation_context": "...",
            "course_id": "...",
            "material_id": "...",
            "page_number": 12
        },
        "metadata": {...}  # optional
    }
    """
    print(f"\nUpload: Lade {len(items)} Dataset-Items hoch...")
    
    for idx, item in enumerate(items, 1):
        try:
            # Validiere, dass 'input' vorhanden ist
            if 'input' not in item:
                print(f"WARNING: Item {idx}: Kein 'input' Feld gefunden, überspringe...")
                continue
            
            input_data = item['input']
            metadata = item.get('metadata', {})
            
            # Erstelle das Dataset-Item
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input=input_data,
                metadata=metadata
            )
            
            print(f"  OK: Item {idx}/{len(items)} hochgeladen: {metadata.get('topic', 'Unbekanntes Thema')}")
            
        except Exception as e:
            print(f"  ERROR: Fehler beim Hochladen von Item {idx}: {e}")
            continue
    
    print(f"\nOK: Dataset-Upload abgeschlossen!")


def main():
    """Hauptfunktion zum Hochladen des Datasets."""
    
    # Prüfe Langfuse Credentials
    public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
    secret_key = os.getenv('LANGFUSE_SECRET_KEY')
    base_url = os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')
    
    if not public_key or not secret_key:
        print("ERROR: LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY müssen in .env gesetzt sein")
        sys.exit(1)
    
    # Initialisiere Langfuse Client
    try:
        langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url
        )
        print("OK: Langfuse Client initialisiert")
    except Exception as e:
        print(f"ERROR: Fehler beim Initialisieren des Langfuse Clients: {e}")
        sys.exit(1)
    
    # Lade Dataset
    script_dir = Path(__file__).parent
    dataset_file = script_dir / "flashcard_prompt_test_dataset_langfuse.json"
    
    try:
        dataset_data = load_dataset(dataset_file)
        print(f"OK: Dataset geladen: {dataset_data.get('description', 'Keine Beschreibung')}")
    except Exception as e:
        print(f"ERROR: Fehler beim Laden des Datasets: {e}")
        sys.exit(1)
    
    # Erstelle Dataset in Langfuse
    dataset_name = dataset_data.get('dataset_name', 'flashcard-agent-math-expressions')
    description = dataset_data.get('description', 'Dataset für Flashcard Agent Prompt Testing')
    
    try:
        create_langfuse_dataset(langfuse_client, dataset_name, description)
    except Exception as e:
        print(f"WARNING: Warnung beim Erstellen des Datasets: {e}")
        print(f"INFO: Versuche fortzufahren...")
    
    # Lade Items hoch
    items = dataset_data.get('items', [])
    if not items:
        print("ERROR: Keine Items im Dataset gefunden!")
        sys.exit(1)
    
    upload_dataset_items(langfuse_client, dataset_name, items)
    
    print(f"\nSUCCESS: Fertig! Das Dataset '{dataset_name}' ist jetzt in Langfuse verfügbar.")
    print(f"\nNächste Schritte:")
    print(f"   1. Öffnen Sie die Langfuse UI")
    print(f"   2. Gehen Sie zu 'Datasets' und wählen Sie '{dataset_name}'")
    print(f"   3. Erstellen Sie ein Prompt Experiment mit diesem Dataset")
    print(f"   4. Stellen Sie sicher, dass Ihr Prompt Template die Variablen verwendet:")
    print(f"      - {{summary}}")
    print(f"      - {{key_terms}}")
    print(f"      - {{exam_questions}}")
    print(f"      - {{diagram_description}}")
    print(f"      - {{conversation_context}}")
    print(f"      - {{course_id}}")
    print(f"      - {{material_id}}")
    print(f"      - {{page_number}}")


if __name__ == "__main__":
    main()
