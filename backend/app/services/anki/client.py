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


@dataclass
class DailyStudyStats:
    """Comprehensive study statistics for a single day"""
    date: str                    # "yyyy-MM-dd" format
    cards_reviewed: int          # Total number of reviews
    time_spent_seconds: int      # Total study time in seconds
    again_count: int             # "Again" button presses (forgotten)
    hard_count: int              # "Hard" button presses
    good_count: int              # "Good" button presses
    easy_count: int              # "Easy" button presses
    new_cards: int               # Cards learned for first time (type=0)
    review_cards: int            # Regular reviews (type=1)
    relearn_cards: int           # Cards being relearned (type=2)
    avg_time_per_card_ms: int    # Average time per review in milliseconds
    
    @property
    def retention_rate(self) -> float:
        """Calculate retention rate: (good + easy) / total"""
        if self.cards_reviewed == 0:
            return 0.0
        return (self.good_count + self.easy_count) / self.cards_reviewed


@dataclass
class CardKnowledge:
    """Knowledge state for a single card"""
    card_id: int
    note_id: int
    deck_name: str
    ease_factor: float      # 1.3-2.5+, higher = easier (stored as permille, e.g., 2500 = 2.5)
    interval: int           # Days until next review
    queue: int              # 0=new, 1=learning, 2=review, -1=suspended, -2=buried
    card_type: int          # 0=new, 1=learning, 2=review, 3=relearning
    reviews: int            # Total review count
    lapses: int             # Times forgotten (pressed "Again")
    
    @property
    def is_mature(self) -> bool:
        """Card is mature if interval >= 21 days"""
        return self.queue == 2 and self.interval >= 21
    
    @property
    def is_young(self) -> bool:
        """Card is young if in review queue but interval < 21 days"""
        return self.queue == 2 and self.interval < 21
    
    @property
    def is_learning(self) -> bool:
        """Card is in learning phase"""
        return self.queue == 1 or self.card_type in (1, 3)
    
    @property
    def is_new(self) -> bool:
        """Card has never been studied"""
        return self.queue == 0 or self.card_type == 0


@dataclass
class DeckKnowledge:
    """Aggregated knowledge metrics for a deck"""
    deck_name: str
    total_cards: int
    new_cards: int
    learning_cards: int
    young_cards: int        # Review queue, interval < 21 days
    mature_cards: int       # Review queue, interval >= 21 days
    suspended_cards: int
    avg_ease: float         # Average ease factor (normalized to 2.5 scale)
    avg_interval: float     # Average interval in days
    total_reviews: int      # Sum of all card reviews
    total_lapses: int       # Sum of all lapses
    mastery_score: float    # Composite 0.0-1.0 score
    is_leaf: bool = True    # True if deck has no subdecks (should be counted in totals)
    
    @property
    def retention_rate(self) -> float:
        """Calculate retention rate: 1 - (lapses / reviews)"""
        if self.total_reviews == 0:
            return 0.0
        return max(0.0, 1.0 - (self.total_lapses / self.total_reviews))
    
    @property
    def status(self) -> str:
        """Get status label based on mastery score"""
        if self.total_cards == 0:
            return "no_cards"
        if self.mastery_score >= 0.8:
            return "mastered"
        if self.mastery_score >= 0.5:
            return "progressing"
        if self.mastery_score >= 0.3:
            return "needs_review"
        return "not_started"


@dataclass
class CourseKnowledge:
    """Aggregated knowledge for a course (multiple decks/lectures)"""
    course_id: str
    course_title: str
    overall_mastery: float
    total_cards: int
    lectures: list[DeckKnowledge]
    weakest_lecture: Optional[str]
    strongest_lecture: Optional[str]


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
    
    def get_detailed_study_history(self, days: int = 90) -> list[DailyStudyStats]:
        """
        Get detailed study statistics aggregated by day.
        
        This method fetches all card reviews and aggregates them by date,
        providing comprehensive statistics including time spent, button presses,
        and card type breakdowns.
        
        Args:
            days: Number of days of history to return (default 90)
            
        Returns:
            List of DailyStudyStats sorted by date (oldest first)
        """
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp_ms = int(cutoff_date.timestamp() * 1000)
        
        # Find all cards that have been reviewed
        # Using "rated:365" to get cards reviewed in last year (covers our needs)
        card_ids = self.find_cards("rated:365")
        
        if not card_ids:
            return []
        
        # Get review history for all cards
        reviews_by_card = self.get_reviews_of_cards(card_ids)
        
        # Aggregate by date
        # Each review is a dict with keys:
        # - id: Unix timestamp (ms) - this is the review time
        # - ease: Button pressed (1=Again, 2=Hard, 3=Good, 4=Easy)
        # - time: Review duration (ms)
        # - type: 0=learn, 1=review, 2=relearn, 3=filtered
        # - ivl, lastIvl, factor, usn: scheduling data
        daily_stats: dict[str, dict] = defaultdict(lambda: {
            "cards_reviewed": 0,
            "time_spent_ms": 0,
            "again_count": 0,
            "hard_count": 0,
            "good_count": 0,
            "easy_count": 0,
            "new_cards": 0,
            "review_cards": 0,
            "relearn_cards": 0,
        })
        
        for card_id, reviews in reviews_by_card.items():
            for review in reviews:
                # Handle both dict format (newer AnkiConnect) and list format (older)
                if isinstance(review, dict):
                    review_time_ms = review.get("id", 0)
                    ease = review.get("ease", 0)
                    review_duration_ms = review.get("time", 0)
                    review_type = review.get("type", 0)
                else:
                    # Legacy list format: [reviewTime, ease, ivl, lastIvl, factor, time, type]
                    review_time_ms = review[0]
                    ease = review[1]
                    review_duration_ms = review[5]
                    review_type = review[6]
                
                # Skip reviews before cutoff
                if review_time_ms < cutoff_timestamp_ms:
                    continue
                
                # Convert timestamp to date string
                review_date = datetime.fromtimestamp(review_time_ms / 1000).strftime("%Y-%m-%d")
                
                stats = daily_stats[review_date]
                stats["cards_reviewed"] += 1
                stats["time_spent_ms"] += review_duration_ms
                
                # Count by button pressed
                if ease == 1:
                    stats["again_count"] += 1
                elif ease == 2:
                    stats["hard_count"] += 1
                elif ease == 3:
                    stats["good_count"] += 1
                elif ease == 4:
                    stats["easy_count"] += 1
                
                # Count by review type
                if review_type == 0:
                    stats["new_cards"] += 1
                elif review_type == 1:
                    stats["review_cards"] += 1
                elif review_type == 2:
                    stats["relearn_cards"] += 1
                # type 3 (filtered) is counted in cards_reviewed but not categorized
        
        # Convert to list of DailyStudyStats
        result = []
        for date_str in sorted(daily_stats.keys()):
            stats = daily_stats[date_str]
            cards = stats["cards_reviewed"]
            avg_time = stats["time_spent_ms"] // cards if cards > 0 else 0
            
            result.append(DailyStudyStats(
                date=date_str,
                cards_reviewed=cards,
                time_spent_seconds=stats["time_spent_ms"] // 1000,
                again_count=stats["again_count"],
                hard_count=stats["hard_count"],
                good_count=stats["good_count"],
                easy_count=stats["easy_count"],
                new_cards=stats["new_cards"],
                review_cards=stats["review_cards"],
                relearn_cards=stats["relearn_cards"],
                avg_time_per_card_ms=avg_time,
            ))
        
        return result
    
    # =========================================================================
    # Card-Level Statistics (for Knowledge Tracking)
    # =========================================================================
    
    def find_cards(self, query: str) -> list[int]:
        """
        Search for cards (not notes) matching a query.
        
        Args:
            query: Search query using Anki's search syntax
                - "deck:MyDeck" - all cards in MyDeck
                - "deck:MyDeck::*" - all cards in MyDeck and subdecks
                - "is:review" - cards in review queue
                - "is:new" - new cards
                
        Returns:
            List of card IDs
        """
        return self._request("findCards", {"query": query})
    
    def get_cards_info(self, card_ids: list[int]) -> list[dict]:
        """
        Get detailed information about cards including scheduling data.
        
        Args:
            card_ids: List of card IDs
            
        Returns:
            List of card info dictionaries containing:
            - cardId, noteId, deckName
            - interval, ease (as permille, e.g., 2500 = 2.5)
            - queue (0=new, 1=learning, 2=review, -1=suspended, -2=buried)
            - type (0=new, 1=learning, 2=review, 3=relearning)
            - reps (review count), lapses
        """
        if not card_ids:
            return []
        return self._request("cardsInfo", {"cards": card_ids})
    
    def get_reviews_of_cards(self, card_ids: list[int]) -> dict[int, list]:
        """
        Get review history for cards.
        
        Args:
            card_ids: List of card IDs
            
        Returns:
            Dictionary mapping card ID to list of reviews.
            Each review is a list: [reviewTime, ease, ivl, lastIvl, factor, time, type]
            - reviewTime: Unix timestamp (ms)
            - ease: Button pressed (1=Again, 2=Hard, 3=Good, 4=Easy)
            - ivl: New interval
            - lastIvl: Previous interval
            - factor: New ease factor (permille)
            - time: Review duration (ms)
            - type: 0=learn, 1=review, 2=relearn, 3=filtered
        """
        if not card_ids:
            return {}
        result = self._request("getReviewsOfCards", {"cards": card_ids})
        # Convert string keys to int
        return {int(k): v for k, v in result.items()}
    
    def get_cards_knowledge(self, deck_name: Optional[str] = None) -> list[CardKnowledge]:
        """
        Get knowledge state for all cards in a deck.
        
        Args:
            deck_name: Deck name to query. If None, queries all decks.
                       Use "DeckName::*" for deck and all subdecks.
                       
        Returns:
            List of CardKnowledge objects
        """
        # Build query
        if deck_name:
            # Escape deck name for query (handle special chars)
            escaped_name = deck_name.replace('"', '\\"')
            query = f'"deck:{escaped_name}"'
        else:
            query = "deck:*"
        
        card_ids = self.find_cards(query)
        if not card_ids:
            return []
        
        cards_info = self.get_cards_info(card_ids)
        
        result = []
        for card in cards_info:
            result.append(CardKnowledge(
                card_id=card["cardId"],
                note_id=card["note"],
                deck_name=card["deckName"],
                ease_factor=card.get("factor", 2500) / 1000.0,  # Convert permille to decimal
                interval=card.get("interval", 0),
                queue=card.get("queue", 0),
                card_type=card.get("type", 0),
                reviews=card.get("reps", 0),
                lapses=card.get("lapses", 0),
            ))
        
        return result
    
    def get_deck_knowledge(self, deck_name: str) -> DeckKnowledge:
        """
        Calculate aggregated knowledge metrics for a single deck.
        
        Args:
            deck_name: Name of the deck
            
        Returns:
            DeckKnowledge with aggregated metrics
        """
        cards = self.get_cards_knowledge(deck_name)
        return self._aggregate_deck_knowledge(deck_name, cards)
    
    def get_all_decks_knowledge(self) -> dict[str, DeckKnowledge]:
        """
        Get knowledge metrics for all decks.
        
        Parent decks (those with subdecks) are marked with is_leaf=False
        to prevent double-counting when calculating totals.
        
        Returns:
            Dictionary mapping deck name to DeckKnowledge
        """
        deck_names = self.get_deck_names()
        
        # Identify parent decks (decks that have subdecks)
        # A deck is a parent if another deck starts with "{deck_name}::"
        parent_decks = set()
        for deck_name in deck_names:
            for other_deck in deck_names:
                if other_deck != deck_name and other_deck.startswith(f"{deck_name}::"):
                    parent_decks.add(deck_name)
                    break
        
        result = {}
        
        for deck_name in deck_names:
            # Skip the default deck if empty
            if deck_name == "Default":
                cards = self.get_cards_knowledge(deck_name)
                if not cards:
                    continue
            
            dk = self.get_deck_knowledge(deck_name)
            
            # Mark parent decks as non-leaf (should not be counted in totals)
            if deck_name in parent_decks:
                # Create a new DeckKnowledge with is_leaf=False
                dk = DeckKnowledge(
                    deck_name=dk.deck_name,
                    total_cards=dk.total_cards,
                    new_cards=dk.new_cards,
                    learning_cards=dk.learning_cards,
                    young_cards=dk.young_cards,
                    mature_cards=dk.mature_cards,
                    suspended_cards=dk.suspended_cards,
                    avg_ease=dk.avg_ease,
                    avg_interval=dk.avg_interval,
                    total_reviews=dk.total_reviews,
                    total_lapses=dk.total_lapses,
                    mastery_score=dk.mastery_score,
                    is_leaf=False,
                )
            
            result[deck_name] = dk
        
        return result
    
    def _aggregate_deck_knowledge(
        self, 
        deck_name: str, 
        cards: list[CardKnowledge]
    ) -> DeckKnowledge:
        """
        Aggregate card-level knowledge into deck-level metrics.
        
        Args:
            deck_name: Name of the deck
            cards: List of CardKnowledge for the deck
            
        Returns:
            DeckKnowledge with calculated metrics
        """
        if not cards:
            return DeckKnowledge(
                deck_name=deck_name,
                total_cards=0,
                new_cards=0,
                learning_cards=0,
                young_cards=0,
                mature_cards=0,
                suspended_cards=0,
                avg_ease=2.5,
                avg_interval=0.0,
                total_reviews=0,
                total_lapses=0,
                mastery_score=0.0,
            )
        
        # Count cards by state
        new_cards = sum(1 for c in cards if c.is_new)
        learning_cards = sum(1 for c in cards if c.is_learning)
        young_cards = sum(1 for c in cards if c.is_young)
        mature_cards = sum(1 for c in cards if c.is_mature)
        suspended_cards = sum(1 for c in cards if c.queue == -1)
        
        # Calculate averages (only for non-new cards)
        reviewed_cards = [c for c in cards if c.reviews > 0]
        if reviewed_cards:
            avg_ease = sum(c.ease_factor for c in reviewed_cards) / len(reviewed_cards)
            avg_interval = sum(c.interval for c in reviewed_cards) / len(reviewed_cards)
        else:
            avg_ease = 2.5
            avg_interval = 0.0
        
        # Sum totals
        total_reviews = sum(c.reviews for c in cards)
        total_lapses = sum(c.lapses for c in cards)
        
        # Calculate mastery score
        mastery_score = self._calculate_mastery_score(
            total_cards=len(cards),
            new_cards=new_cards,
            learning_cards=learning_cards,
            young_cards=young_cards,
            mature_cards=mature_cards,
            avg_ease=avg_ease,
            total_reviews=total_reviews,
            total_lapses=total_lapses,
        )
        
        return DeckKnowledge(
            deck_name=deck_name,
            total_cards=len(cards),
            new_cards=new_cards,
            learning_cards=learning_cards,
            young_cards=young_cards,
            mature_cards=mature_cards,
            suspended_cards=suspended_cards,
            avg_ease=avg_ease,
            avg_interval=avg_interval,
            total_reviews=total_reviews,
            total_lapses=total_lapses,
            mastery_score=mastery_score,
        )
    
    def _calculate_mastery_score(
        self,
        total_cards: int,
        new_cards: int,
        learning_cards: int,
        young_cards: int,
        mature_cards: int,
        avg_ease: float,
        total_reviews: int,
        total_lapses: int,
    ) -> float:
        """
        Calculate composite mastery score (0.0-1.0).
        
        Formula weights:
        - 40% card distribution (mature > young > learning > new)
        - 30% ease factor (normalized)
        - 30% retention rate (1 - lapse rate)
        """
        if total_cards == 0:
            return 0.0
        
        # Distribution score: weighted average of card states
        distribution_score = (
            mature_cards * 1.0 +
            young_cards * 0.6 +
            learning_cards * 0.3 +
            new_cards * 0.0
        ) / total_cards
        
        # Ease score: normalize 1.3-3.0 range to 0-1
        ease_score = max(0.0, min(1.0, (avg_ease - 1.3) / 1.7))
        
        # Retention score
        if total_reviews > 0:
            retention_score = max(0.0, 1.0 - (total_lapses / total_reviews))
        else:
            retention_score = 0.0
        
        # Weighted combination
        mastery = (
            0.4 * distribution_score +
            0.3 * ease_score +
            0.3 * retention_score
        )
        
        return round(mastery, 3)
    
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
    
    def get_deck_notes_with_info(self, parent_deck: str) -> list[dict]:
        """
        Get all notes in a deck hierarchy with full info including mod timestamp.
        
        Used for syncing Anki → Cache.
        
        Args:
            parent_deck: Parent deck name (queries parent::*)
            
        Returns:
            List of note info dicts with: noteId, fields, tags, mod, etc.
        """
        # Query all notes in deck hierarchy
        escaped_name = parent_deck.replace('"', '\\"')
        query = f'"deck:{escaped_name}::*"'
        
        note_ids = self.find_notes(query)
        
        if not note_ids:
            # Also try exact deck match
            query = f'"deck:{escaped_name}"'
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
    
    # =========================================================================
    # Deduplication & Deck Management
    # =========================================================================
    
    def get_deck_card_fronts(self, parent_deck: str) -> list[str]:
        """
        Get all card front texts from a parent deck and its sub-decks.
        
        Used for deduplication during flashcard generation.
        
        Args:
            parent_deck: Parent deck name (course), e.g., "Marketing 101"
                        Queries all sub-decks (lectures) within it.
        
        Returns:
            List of front text from all cards in the deck hierarchy
        """
        # Query all notes in deck hierarchy (parent::*)
        # Escape quotes in deck name
        escaped_name = parent_deck.replace('"', '\\"')
        query = f'"deck:{escaped_name}::*"'
        
        note_ids = self.find_notes(query)
        
        if not note_ids:
            # Also try exact deck match (in case there are cards directly in parent)
            query = f'"deck:{escaped_name}"'
            note_ids = self.find_notes(query)
            if not note_ids:
                return []
        
        # Get note info including fields
        notes_info = self.get_notes_info(note_ids)
        
        # Extract front field values
        fronts = []
        for note in notes_info:
            fields = note.get("fields", {})
            front_field = fields.get("Front", {})
            if front_field:
                value = front_field.get("value", "")
                if value:
                    fronts.append(value)
        
        return fronts
    
    def rename_deck(self, old_name: str, new_name: str) -> bool:
        """
        Rename an Anki deck by moving all cards to a new deck.
        
        Preserves all card history, scheduling, and learning state.
        
        Args:
            old_name: Current deck name
            new_name: New deck name
            
        Returns:
            True if successful, False if no cards found
        """
        # Find all cards in the old deck
        escaped_old = old_name.replace('"', '\\"')
        card_ids = self.find_cards(f'"deck:{escaped_old}"')
        
        if not card_ids:
            return False
        
        # Create the new deck (Anki auto-creates parent hierarchy)
        self.create_deck(new_name)
        
        # Move all cards to the new deck
        self._request("changeDeck", {"cards": card_ids, "deck": new_name})
        
        # Optionally delete the old empty deck
        # self._request("deleteDecks", {"decks": [old_name], "cardsToo": False})
        
        return True
    
    def delete_deck_with_cards(
        self, 
        deck_name: str, 
        i_understand_this_is_permanent: bool = False
    ) -> bool:
        """
        ⚠️  DANGEROUS: Delete a deck and ALL its cards from Anki.
        
        This action is IRREVERSIBLE and will delete from AnkiWeb on next sync!
        
        Args:
            deck_name: Deck name to delete
            i_understand_this_is_permanent: Must be True to proceed
            
        Returns:
            True if successful, False if blocked
            
        Raises:
            ValueError: If confirmation not provided
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not i_understand_this_is_permanent:
            logger.error(
                f"⛔ BLOCKED: Attempted to delete deck '{deck_name}' without confirmation. "
                f"Set i_understand_this_is_permanent=True to proceed."
            )
            raise ValueError(
                f"Deletion of deck '{deck_name}' blocked. "
                f"This would permanently delete all cards from Anki AND AnkiWeb. "
                f"Set i_understand_this_is_permanent=True if you really want this."
            )
        
        # Get card count before deletion for logging
        try:
            card_ids = self.find_cards(f'"deck:{deck_name}"')
            card_count = len(card_ids) if card_ids else 0
        except:
            card_count = "unknown"
        
        logger.warning(
            f"🗑️  DELETING DECK: '{deck_name}' with {card_count} cards. "
            f"This will sync to AnkiWeb and is PERMANENT!"
        )
        
        self._request("deleteDecks", {"decks": [deck_name], "cardsToo": True})
        
        logger.warning(f"🗑️  DELETED: Deck '{deck_name}' has been permanently deleted.")
        return True
    
    def delete_notes(
        self, 
        note_ids: list[int],
        i_understand_this_is_permanent: bool = False
    ) -> bool:
        """
        ⚠️  DANGEROUS: Delete notes from Anki.
        
        This action is IRREVERSIBLE and will delete from AnkiWeb on next sync!
        
        Args:
            note_ids: List of note IDs to delete
            i_understand_this_is_permanent: Must be True to proceed
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If confirmation not provided
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not i_understand_this_is_permanent:
            logger.error(
                f"⛔ BLOCKED: Attempted to delete {len(note_ids)} notes without confirmation."
            )
            raise ValueError(
                f"Deletion of {len(note_ids)} notes blocked. "
                f"This would permanently delete from Anki AND AnkiWeb. "
                f"Set i_understand_this_is_permanent=True if you really want this."
            )
        
        logger.warning(
            f"🗑️  DELETING {len(note_ids)} NOTES. "
            f"This will sync to AnkiWeb and is PERMANENT!"
        )
        
        self._request("deleteNotes", {"notes": note_ids})
        
        logger.warning(f"🗑️  DELETED: {len(note_ids)} notes permanently deleted.")
        return True


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
