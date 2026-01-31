"""
AnkiConnect API Client

Wrapper for the AnkiConnect HTTP API.
- On Apple Silicon Macs: Uses native Anki app with AnkiConnect add-on
- On Linux/Windows/Intel Mac: Uses headless Docker container

API documentation: https://foosoft.net/projects/anki-connect/
"""

import json
import subprocess
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


class AnkiError(Exception):
    """Exception raised when AnkiConnect returns an error"""
    pass


class AnkiConnectionError(Exception):
    """Exception raised when unable to connect to AnkiConnect"""
    pass


@dataclass
class DeckStats:
    """Statistics for a single deck"""
    deck_id: int
    name: str
    total_cards: int
    new_cards: int
    learning_cards: int
    review_cards: int


@dataclass
class ReviewStats:
    """Review statistics"""
    cards_reviewed_today: int
    reviews_by_day: dict[str, int]  # date -> count


class AnkiClient:
    """
    Client for interacting with AnkiConnect API.
    
    Usage:
        client = AnkiClient()
        client.ensure_running()
        
        # Get stats
        stats = client.get_deck_stats(["Default"])
        
        # Add a card
        note_id = client.add_note("MyDeck", "Question?", "Answer!")
        
        # Sync to AnkiWeb
        client.sync()
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765, timeout: int = 30):
        self.url = f"http://{host}:{port}"
        self.timeout = timeout
        self._project_root = self._find_project_root()
    
    def _find_project_root(self) -> Path:
        """Find the project root directory (where docker-compose.yml lives)"""
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "docker-compose.yml").exists():
                return parent
        # Fallback to Group3 directory
        return Path(__file__).resolve().parents[4]
    
    def _request(self, action: str, params: Optional[dict] = None) -> Any:
        """
        Make a request to the AnkiConnect API.
        
        Args:
            action: The AnkiConnect action name
            params: Optional parameters for the action
            
        Returns:
            The result from AnkiConnect
            
        Raises:
            AnkiError: If AnkiConnect returns an error
            AnkiConnectionError: If unable to connect to AnkiConnect
        """
        payload = {
            "action": action,
            "version": 6,
        }
        if params:
            payload["params"] = params
        
        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise AnkiConnectionError(
                f"Cannot connect to AnkiConnect at {self.url}. "
                "Make sure Anki is running with the AnkiConnect add-on installed."
            ) from e
        except Exception as e:
            raise AnkiConnectionError(f"Request to AnkiConnect failed: {e}") from e
        
        if result.get("error"):
            raise AnkiError(result["error"])
        
        return result.get("result")
    
    # =========================================================================
    # Container Management
    # =========================================================================
    
    def is_running(self) -> bool:
        """Check if AnkiConnect is responding"""
        try:
            self._request("version")
            return True
        except (AnkiConnectionError, Exception):
            return False
    
    def ensure_running(self, max_wait: int = 30) -> bool:
        """
        Ensure Anki/AnkiConnect is running.
        
        On Apple Silicon Macs: Tries to open the native Anki app.
        On other platforms: Tries to start the Docker container.
        
        Args:
            max_wait: Maximum seconds to wait for Anki to start
            
        Returns:
            True if Anki is running
            
        Raises:
            AnkiConnectionError: If Anki fails to start
        """
        if self.is_running():
            return True
        
        # Detect platform
        import platform
        is_apple_silicon = (
            platform.system() == "Darwin" and 
            platform.machine() == "arm64"
        )
        
        if is_apple_silicon:
            # Try to open native Anki app on macOS
            print("Starting native Anki app...")
            try:
                subprocess.run(
                    ["open", "-a", "Anki"],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError:
                raise AnkiConnectionError(
                    "Failed to start Anki. Please install Anki from https://apps.ankiweb.net/ "
                    "and install the AnkiConnect add-on (code: 2055492159)"
                )
            except FileNotFoundError:
                raise AnkiConnectionError(
                    "Anki not found. Please install from https://apps.ankiweb.net/"
                )
        else:
            # Try Docker on other platforms
            print("Starting Anki container...")
            try:
                subprocess.run(
                    ["docker", "compose", "up", "-d"],
                    cwd=self._project_root,
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                raise AnkiConnectionError(
                    f"Failed to start Anki container: {e.stderr.decode()}"
                ) from e
            except FileNotFoundError:
                raise AnkiConnectionError(
                    "Docker not found. Please install Docker Desktop."
                )
        
        # Wait for AnkiConnect to be ready
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self.is_running():
                print("Anki ready!")
                return True
            time.sleep(1)
        
        if is_apple_silicon:
            raise AnkiConnectionError(
                f"AnkiConnect did not respond within {max_wait} seconds. "
                "Please ensure Anki is running and AnkiConnect add-on is installed (code: 2055492159)"
            )
        else:
            raise AnkiConnectionError(
                f"Anki container did not start within {max_wait} seconds"
            )
    
    def stop(self) -> None:
        """Stop the Anki container"""
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=self._project_root,
            check=True,
            capture_output=True
        )
    
    def is_first_run(self) -> bool:
        """Check if this is the first run (no Anki profile exists)"""
        profile_path = self._project_root / "anki-data" / "User 1" / "collection.anki2"
        return not profile_path.exists()
    
    # =========================================================================
    # Statistics (Read)
    # =========================================================================
    
    def get_deck_names(self) -> list[str]:
        """Get list of all deck names"""
        return self._request("deckNames")
    
    def get_deck_stats(self, deck_names: Optional[list[str]] = None) -> dict[str, DeckStats]:
        """
        Get statistics for specified decks.
        
        Args:
            deck_names: List of deck names. If None, gets all decks.
            
        Returns:
            Dictionary mapping deck name to DeckStats
        """
        if deck_names is None:
            deck_names = self.get_deck_names()
        
        raw_stats = self._request("getDeckStats", {"decks": deck_names})
        
        result = {}
        for deck_id_str, stats in raw_stats.items():
            result[stats["name"]] = DeckStats(
                deck_id=int(deck_id_str),
                name=stats["name"],
                total_cards=stats.get("total_in_deck", 0),
                new_cards=stats.get("new_count", 0),
                learning_cards=stats.get("learn_count", 0),
                review_cards=stats.get("review_count", 0),
            )
        
        return result
    
    def get_cards_reviewed_today(self) -> int:
        """Get the number of cards reviewed today"""
        return self._request("getNumCardsReviewedToday")
    
    def get_reviews_by_day(self) -> dict[str, int]:
        """
        Get review counts by day.
        
        Returns:
            Dictionary mapping date string to review count
        """
        result = self._request("getNumCardsReviewedByDay")
        return {str(item[0]): item[1] for item in result}
    
    def get_collection_stats_html(self, whole_collection: bool = True) -> str:
        """
        Get the collection statistics as HTML.
        
        Args:
            whole_collection: If True, include all decks
            
        Returns:
            HTML string of statistics
        """
        return self._request("getCollectionStatsHTML", {
            "wholeCollection": whole_collection
        })
    
    def get_review_stats(self) -> ReviewStats:
        """Get comprehensive review statistics"""
        return ReviewStats(
            cards_reviewed_today=self.get_cards_reviewed_today(),
            reviews_by_day=self.get_reviews_by_day()
        )
    
    # =========================================================================
    # Flashcard Creation (Write)
    # =========================================================================
    
    def create_deck(self, name: str) -> int:
        """
        Create a new deck.
        
        Args:
            name: Deck name (use "::" for nested decks, e.g., "Parent::Child")
            
        Returns:
            Deck ID
        """
        return self._request("createDeck", {"deck": name})
    
    def add_note(
        self,
        deck: str,
        front: str,
        back: str,
        tags: Optional[list[str]] = None,
        model: str = "Basic",
        allow_duplicate: bool = False
    ) -> int:
        """
        Add a single flashcard note.
        
        Args:
            deck: Deck name to add card to
            front: Front side content
            back: Back side content
            tags: Optional list of tags
            model: Note model (default "Basic")
            allow_duplicate: Allow duplicate cards
            
        Returns:
            Note ID
        """
        return self._request("addNote", {
            "note": {
                "deckName": deck,
                "modelName": model,
                "fields": {
                    "Front": front,
                    "Back": back
                },
                "tags": tags or [],
                "options": {
                    "allowDuplicate": allow_duplicate
                }
            }
        })
    
    def add_notes(
        self,
        notes: list[dict],
        deck: Optional[str] = None,
        model: str = "Basic"
    ) -> list[Optional[int]]:
        """
        Add multiple flashcard notes in batch.
        
        Args:
            notes: List of dicts with keys: front, back, tags (optional), deck (optional)
            deck: Default deck if not specified per note
            model: Note model (default "Basic")
            
        Returns:
            List of note IDs (None for failed additions)
        """
        formatted_notes = []
        for note in notes:
            formatted_notes.append({
                "deckName": note.get("deck", deck),
                "modelName": model,
                "fields": {
                    "Front": note["front"],
                    "Back": note["back"]
                },
                "tags": note.get("tags", []),
                "options": {
                    "allowDuplicate": False
                }
            })
        
        return self._request("addNotes", {"notes": formatted_notes})
    
    def add_note_with_cloze(
        self,
        deck: str,
        text: str,
        tags: Optional[list[str]] = None
    ) -> int:
        """
        Add a cloze deletion card.
        
        Args:
            deck: Deck name
            text: Text with cloze markers, e.g., "{{c1::Paris}} is the capital of France"
            tags: Optional tags
            
        Returns:
            Note ID
        """
        return self._request("addNote", {
            "note": {
                "deckName": deck,
                "modelName": "Cloze",
                "fields": {
                    "Text": text,
                    "Extra": ""
                },
                "tags": tags or [],
                "options": {
                    "allowDuplicate": False
                }
            }
        })
    
    # =========================================================================
    # Card Search
    # =========================================================================
    
    def find_notes(self, query: str) -> list[int]:
        """
        Search for notes matching a query.
        
        Query examples:
            - "deck:MyDeck" - all notes in MyDeck
            - "tag:important" - notes with 'important' tag
            - "front:*python*" - notes with 'python' in front
            - "is:due" - cards that are due
            
        Returns:
            List of note IDs
        """
        return self._request("findNotes", {"query": query})
    
    def get_notes_info(self, note_ids: list[int]) -> list[dict]:
        """
        Get detailed information about notes.
        
        Args:
            note_ids: List of note IDs
            
        Returns:
            List of note info dictionaries
        """
        return self._request("notesInfo", {"notes": note_ids})
    
    def search_notes(self, query: str) -> list[dict]:
        """
        Search for notes and return their full info.
        
        Convenience method combining find_notes and get_notes_info.
        """
        note_ids = self.find_notes(query)
        if not note_ids:
            return []
        return self.get_notes_info(note_ids)
    
    # =========================================================================
    # Sync
    # =========================================================================
    
    def sync(self) -> None:
        """
        Trigger sync with AnkiWeb.
        
        Note: Requires AnkiWeb login to be configured first.
        Use the VNC interface (localhost:5900) for initial setup.
        """
        self._request("sync")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_version(self) -> int:
        """Get AnkiConnect version"""
        return self._request("version")
    
    def get_model_names(self) -> list[str]:
        """Get list of available note models/types"""
        return self._request("modelNames")
    
    def store_media_file(
        self,
        filename: str,
        data: Optional[str] = None,
        path: Optional[str] = None,
        url: Optional[str] = None
    ) -> str:
        """
        Store a media file in Anki's media folder.
        
        Provide ONE of: data (base64), path (local file), or url
        
        Returns:
            Stored filename
        """
        params = {"filename": filename}
        if data:
            params["data"] = data
        elif path:
            params["path"] = path
        elif url:
            params["url"] = url
        else:
            raise ValueError("Must provide data, path, or url")
        
        return self._request("storeMediaFile", params)


def print_first_run_instructions():
    """Print instructions for first-time AnkiWeb setup"""
    print("=" * 60)
    print("FIRST-TIME ANKI SETUP REQUIRED")
    print("=" * 60)
    print()
    print("To sync cards to your phone, you need to login to AnkiWeb once:")
    print()
    print("1. Open VNC viewer or run: open vnc://localhost:5900")
    print("2. In the Anki window, click the 'Sync' button")
    print("3. Enter your AnkiWeb email and password")
    print("4. Close the VNC window - you won't need it again")
    print()
    print("Your credentials are saved locally in ./anki-data/")
    print("=" * 60)
