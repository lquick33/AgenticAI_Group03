"""
Knowledge Tracking Service

Provides course-level knowledge aggregation and tracking based on Anki data.
Maps courses and course_materials to Anki decks and calculates mastery scores.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from .client import (
    AnkiClient, 
    DeckKnowledge, 
    CourseKnowledge,
    AnkiConnectionError,
    AnkiError,
)

logger = logging.getLogger(__name__)


def build_deck_name(course_title: str, material_name: str) -> str:
    """
    Build hierarchical deck name from course and material.
    
    Args:
        course_title: Course title, e.g., "Marketing 101"
        material_name: Material filename, e.g., "Lecture 1 - Introduction.pdf"
        
    Returns:
        Deck name: "Marketing 101::Lecture 1 - Introduction"
    """
    # Remove file extension
    lecture_name = Path(material_name).stem
    return f"{course_title}::{lecture_name}"


def parse_deck_name(deck_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a deck name into course and lecture parts.
    
    Args:
        deck_name: Full deck name, e.g., "Marketing 101::Lecture 1 - Introduction"
        
    Returns:
        Tuple of (course_title, lecture_name) or (None, None) if not parseable
    """
    if "::" not in deck_name:
        return None, None
    
    parts = deck_name.split("::", 1)
    return parts[0], parts[1] if len(parts) > 1 else None


@dataclass
class LectureKnowledge:
    """Knowledge metrics for a single lecture/material"""
    material_id: Optional[str]
    name: str
    deck_name: str
    mastery_score: float
    total_cards: int
    new_cards: int
    learning_cards: int
    young_cards: int
    mature_cards: int
    avg_ease: float
    avg_interval_days: float
    retention_rate: float
    status: str


@dataclass
class CourseKnowledgeResult:
    """Complete knowledge result for a course"""
    status: str
    course_id: str
    course_title: str
    overall_mastery: float
    total_cards: int
    lectures: list[LectureKnowledge]
    weakest_lecture: Optional[str]
    strongest_lecture: Optional[str]
    recommendations: list[str]


class KnowledgeService:
    """
    Service for tracking user knowledge levels based on Anki data.
    
    Provides methods to:
    - Get knowledge levels for all decks
    - Get knowledge levels for a specific course (with per-lecture breakdown)
    - Save knowledge snapshots for trend analysis
    """
    
    def __init__(self, anki_client: Optional[AnkiClient] = None):
        """
        Initialize the knowledge service.
        
        Args:
            anki_client: Optional AnkiClient instance. If None, creates a new one.
        """
        self.anki = anki_client or AnkiClient()
    
    def get_all_knowledge_levels(self) -> dict:
        """
        Get knowledge levels for all Anki decks.
        
        Returns:
            Dictionary with status, overall mastery, and per-deck breakdown
        """
        try:
            self.anki.ensure_running()
        except AnkiConnectionError as e:
            return {"status": "error", "error": str(e)}
        
        try:
            deck_knowledge = self.anki.get_all_decks_knowledge()
            
            if not deck_knowledge:
                return {
                    "status": "success",
                    "overall_mastery": 0.0,
                    "decks": {},
                    "recommendations": ["No decks found. Create some flashcards to get started!"]
                }
            
            # IMPORTANT: Only count leaf decks (is_leaf=True) in totals
            # Parent decks contain the same cards as their subdecks, so counting
            # them would result in double-counting
            leaf_decks = {name: dk for name, dk in deck_knowledge.items() if dk.is_leaf}
            
            # Calculate overall mastery (weighted by card count) - ONLY from leaf decks
            total_cards = sum(dk.total_cards for dk in leaf_decks.values())
            if total_cards > 0:
                overall_mastery = sum(
                    dk.mastery_score * dk.total_cards 
                    for dk in leaf_decks.values()
                ) / total_cards
            else:
                overall_mastery = 0.0
            
            # Format deck data (include all decks for display, but mark parents)
            decks = {}
            for name, dk in deck_knowledge.items():
                decks[name] = {
                    "mastery_score": dk.mastery_score,
                    "total_cards": dk.total_cards,
                    "new_cards": dk.new_cards,
                    "learning_cards": dk.learning_cards,
                    "young_cards": dk.young_cards,
                    "mature_cards": dk.mature_cards,
                    "avg_ease": round(dk.avg_ease, 2),
                    "avg_interval_days": round(dk.avg_interval, 1),
                    "retention_rate": round(dk.retention_rate, 2),
                    "status": dk.status,
                    "is_leaf": dk.is_leaf,  # Include flag so consumers know this is a parent
                }
            
            # Generate recommendations (only from leaf decks to avoid duplicates)
            recommendations = self._generate_recommendations(leaf_decks)
            
            return {
                "status": "success",
                "overall_mastery": round(overall_mastery, 2),
                "total_cards": total_cards,  # Add total for convenience
                "decks": decks,
                "recommendations": recommendations,
            }
            
        except AnkiError as e:
            return {"status": "error", "error": str(e)}
    
    def get_course_knowledge(
        self,
        course_id: str,
        course_title: str,
        materials: list[dict],
    ) -> CourseKnowledgeResult:
        """
        Get knowledge levels for a specific course with per-lecture breakdown.
        
        Args:
            course_id: UUID of the course
            course_title: Title of the course
            materials: List of course materials with keys: id, file_name
            
        Returns:
            CourseKnowledgeResult with per-lecture breakdown
        """
        try:
            self.anki.ensure_running()
        except AnkiConnectionError as e:
            return CourseKnowledgeResult(
                status="error",
                course_id=course_id,
                course_title=course_title,
                overall_mastery=0.0,
                total_cards=0,
                lectures=[],
                weakest_lecture=None,
                strongest_lecture=None,
                recommendations=[f"Could not connect to Anki: {e}"],
            )
        
        try:
            lectures = []
            total_cards = 0
            weighted_mastery_sum = 0.0
            
            for material in materials:
                material_id = material.get("id")
                file_name = material.get("file_name", "Unknown")
                deck_name = build_deck_name(course_title, file_name)
                lecture_name = Path(file_name).stem
                
                # Try to get knowledge for this deck
                try:
                    dk = self.anki.get_deck_knowledge(deck_name)
                except AnkiError:
                    # Deck might not exist yet
                    dk = DeckKnowledge(
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
                
                lecture = LectureKnowledge(
                    material_id=material_id,
                    name=lecture_name,
                    deck_name=deck_name,
                    mastery_score=dk.mastery_score,
                    total_cards=dk.total_cards,
                    new_cards=dk.new_cards,
                    learning_cards=dk.learning_cards,
                    young_cards=dk.young_cards,
                    mature_cards=dk.mature_cards,
                    avg_ease=round(dk.avg_ease, 2),
                    avg_interval_days=round(dk.avg_interval, 1),
                    retention_rate=round(dk.retention_rate, 2),
                    status=dk.status,
                )
                lectures.append(lecture)
                
                total_cards += dk.total_cards
                weighted_mastery_sum += dk.mastery_score * dk.total_cards
            
            # Calculate overall course mastery
            if total_cards > 0:
                overall_mastery = weighted_mastery_sum / total_cards
            else:
                overall_mastery = 0.0
            
            # Find weakest and strongest lectures (with cards)
            lectures_with_cards = [l for l in lectures if l.total_cards > 0]
            if lectures_with_cards:
                weakest = min(lectures_with_cards, key=lambda l: l.mastery_score)
                strongest = max(lectures_with_cards, key=lambda l: l.mastery_score)
                weakest_lecture = weakest.name
                strongest_lecture = strongest.name
            else:
                weakest_lecture = None
                strongest_lecture = None
            
            # Generate course-specific recommendations
            recommendations = self._generate_course_recommendations(
                course_title, lectures, overall_mastery
            )
            
            return CourseKnowledgeResult(
                status="success",
                course_id=course_id,
                course_title=course_title,
                overall_mastery=round(overall_mastery, 2),
                total_cards=total_cards,
                lectures=lectures,
                weakest_lecture=weakest_lecture,
                strongest_lecture=strongest_lecture,
                recommendations=recommendations,
            )
            
        except AnkiError as e:
            return CourseKnowledgeResult(
                status="error",
                course_id=course_id,
                course_title=course_title,
                overall_mastery=0.0,
                total_cards=0,
                lectures=[],
                weakest_lecture=None,
                strongest_lecture=None,
                recommendations=[f"Anki error: {e}"],
            )
    
    def _generate_recommendations(
        self, 
        deck_knowledge: dict[str, DeckKnowledge]
    ) -> list[str]:
        """Generate study recommendations based on deck knowledge."""
        recommendations = []
        
        for name, dk in deck_knowledge.items():
            if dk.total_cards == 0:
                continue
            
            # Recommend reviewing decks with low mastery
            if dk.mastery_score < 0.5 and dk.learning_cards > 0:
                recommendations.append(
                    f"Focus on '{name}' - {dk.learning_cards} cards still in learning phase"
                )
            
            # Recommend decks with many new cards
            if dk.new_cards > 10:
                recommendations.append(
                    f"'{name}' has {dk.new_cards} new cards waiting to be studied"
                )
            
            # Celebrate mastered decks
            if dk.mastery_score >= 0.8:
                recommendations.append(
                    f"'{name}' is well mastered ({int(dk.mastery_score * 100)}%) - consider maintenance mode"
                )
        
        # Limit recommendations
        return recommendations[:5]
    
    def _generate_course_recommendations(
        self,
        course_title: str,
        lectures: list[LectureKnowledge],
        overall_mastery: float,
    ) -> list[str]:
        """Generate course-specific study recommendations."""
        recommendations = []
        
        # Find lectures needing attention
        needs_review = [l for l in lectures if l.status == "needs_review"]
        not_started = [l for l in lectures if l.status == "not_started" or l.total_cards == 0]
        progressing = [l for l in lectures if l.status == "progressing"]
        
        # Prioritize lectures with low retention
        low_retention = [l for l in lectures if l.retention_rate < 0.7 and l.total_cards > 0]
        if low_retention:
            worst = min(low_retention, key=lambda l: l.retention_rate)
            recommendations.append(
                f"Review '{worst.name}' - retention rate is only {int(worst.retention_rate * 100)}%"
            )
        
        # Recommend focusing on needs_review lectures
        if needs_review:
            recommendations.append(
                f"Focus on '{needs_review[0].name}' - {needs_review[0].new_cards} new cards and low mastery"
            )
        
        # Mention lectures without flashcards
        if not_started:
            names = ", ".join(l.name for l in not_started[:2])
            recommendations.append(
                f"Create flashcards for: {names}"
            )
        
        # Encourage progress on in-progress lectures
        if progressing:
            best_progressing = max(progressing, key=lambda l: l.mastery_score)
            recommendations.append(
                f"Keep studying '{best_progressing.name}' - almost there ({int(best_progressing.mastery_score * 100)}%)"
            )
        
        # Overall encouragement
        if overall_mastery >= 0.7:
            recommendations.append(
                f"Great progress on {course_title}! Overall mastery: {int(overall_mastery * 100)}%"
            )
        
        return recommendations[:5]
    
    def to_snapshot_dict(self, dk: DeckKnowledge, user_id: str) -> dict:
        """Convert DeckKnowledge to a dictionary for database storage."""
        return {
            "user_id": user_id,
            "deck_name": dk.deck_name,
            "total_cards": dk.total_cards,
            "new_cards": dk.new_cards,
            "learning_cards": dk.learning_cards,
            "young_cards": dk.young_cards,
            "mature_cards": dk.mature_cards,
            "suspended_cards": dk.suspended_cards,
            "avg_ease_factor": dk.avg_ease,
            "avg_interval_days": dk.avg_interval,
            "retention_rate": dk.retention_rate,
            "mastery_score": dk.mastery_score,
        }
