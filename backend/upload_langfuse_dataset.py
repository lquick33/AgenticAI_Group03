"""Upload repo-local datasets to Langfuse.

Supports both the legacy flashcard dataset format (`items`) and the Tutor eval
format (`cases`).

Usage:
    python upload_langfuse_dataset.py
    python upload_langfuse_dataset.py --dataset-file evals/tutor_gold_v1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

try:
    from langfuse import Langfuse
except ImportError:
    print("ERROR: Langfuse ist nicht installiert. Bitte installieren Sie es mit: pip install langfuse")
    sys.exit(1)

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
DEFAULT_FLASHCARD_DATASET = PROJECT_ROOT / "flashcard_prompt_test_dataset_langfuse.json"


def load_json(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset-Datei nicht gefunden: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def prepare_upload_payload(file_path: Path) -> Dict[str, Any]:
    raw_dataset = load_json(file_path)

    if "cases" in raw_dataset and "schema_version" in raw_dataset:
        from evals.tutor_eval import load_tutor_eval_dataset, prepare_langfuse_upload_payload

        dataset = load_tutor_eval_dataset(file_path)
        return prepare_langfuse_upload_payload(dataset)

    if "items" not in raw_dataset:
        raise ValueError("Unbekanntes Dataset-Format: erwartet 'items' oder 'cases'.")

    return {
        "dataset_name": raw_dataset.get("dataset_name", file_path.stem),
        "description": raw_dataset.get("description", "Langfuse dataset upload"),
        "items": raw_dataset.get("items", []),
    }


def create_langfuse_dataset(
    langfuse_client: Langfuse,
    dataset_name: str,
    description: str | None = None,
) -> str:
    try:
        dataset = langfuse_client.create_dataset(name=dataset_name, description=description)
        print(f"OK: Dataset '{dataset_name}' erstellt")
        return dataset.id
    except Exception as exc:
        print(f"WARNING: Fehler beim Erstellen (moeglicherweise existiert es bereits): {exc}")
        print(f"INFO: Bitte pruefen Sie in der Langfuse UI, ob das Dataset '{dataset_name}' bereits existiert")
        return dataset_name


def upload_dataset_items(
    langfuse_client: Langfuse,
    dataset_name: str,
    items: List[Dict[str, Any]],
) -> None:
    print(f"\nUpload: Lade {len(items)} Dataset-Items hoch...")

    for idx, item in enumerate(items, 1):
        try:
            if "input" not in item:
                print(f"WARNING: Item {idx}: Kein 'input' Feld gefunden, ueberspringe...")
                continue

            input_data = item["input"]
            metadata = item.get("metadata", {})
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input=input_data,
                metadata=metadata,
            )
            label = metadata.get("case_id") or metadata.get("topic") or f"item-{idx}"
            print(f"  OK: Item {idx}/{len(items)} hochgeladen: {label}")
        except Exception as exc:
            print(f"  ERROR: Fehler beim Hochladen von Item {idx}: {exc}")
            continue

    print("\nOK: Dataset-Upload abgeschlossen!")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a local dataset to Langfuse.")
    parser.add_argument(
        "--dataset-file",
        type=Path,
        default=DEFAULT_FLASHCARD_DATASET,
        help="Pfad zur Dataset-Datei (JSON).",
    )
    args = parser.parse_args()

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        print("ERROR: LANGFUSE_PUBLIC_KEY und LANGFUSE_SECRET_KEY muessen in .env gesetzt sein")
        return 1

    try:
        langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url,
        )
        print("OK: Langfuse Client initialisiert")
    except Exception as exc:
        print(f"ERROR: Fehler beim Initialisieren des Langfuse Clients: {exc}")
        return 1

    try:
        payload = prepare_upload_payload(args.dataset_file)
        print(f"OK: Dataset geladen: {payload.get('description', 'Keine Beschreibung')}")
    except Exception as exc:
        print(f"ERROR: Fehler beim Laden des Datasets: {exc}")
        return 1

    dataset_name = payload["dataset_name"]
    description = payload.get("description")
    items = payload.get("items", [])
    if not items:
        print("ERROR: Keine Items im Dataset gefunden!")
        return 1

    try:
        create_langfuse_dataset(langfuse_client, dataset_name, description)
    except Exception as exc:
        print(f"WARNING: Warnung beim Erstellen des Datasets: {exc}")
        print("INFO: Versuche fortzufahren...")

    upload_dataset_items(langfuse_client, dataset_name, items)
    print(f"\nSUCCESS: Fertig! Das Dataset '{dataset_name}' ist jetzt in Langfuse verfuegbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
