"""Quest manager for handling collections of quests."""

from typing import List, Dict, Optional, Iterator, Any
from datetime import datetime
from .quest import Quest
from .interface import AllQuestsResponse


class QuestManager:
    """Manages a collection of quests."""

    def __init__(self, quests: Optional[List[Quest]] = None):
        """Initialize quest manager.
        
        Args:
            quests: Optional list of quests to initialize with
        """
        self._quests: Dict[str, Quest] = {}
        if quests:
            for quest in quests:
                self._quests[quest.id] = quest

    @classmethod
    def from_response(
        cls,
        response: AllQuestsResponse,
        user_id: str = '',
        fetch_excluded: bool = False,
    ) -> 'QuestManager':
        """Create QuestManager from API response.
        
        Args:
            response: API response containing quests
            user_id: User ID for context
            fetch_excluded: Whether to include excluded quests
            
        Returns:
            QuestManager instance. A temporary enrollment block only prevents
            enrolling, so it never hides the quests already on the account;
            callers can read ``response.quest_enrollment_blocked_until``.
        """
        quests = [Quest(quest) for quest in response.quests]
        manager = cls(quests)
        
        if fetch_excluded:
            for excluded_quest in response.excluded_quests:
                manager.add_excluded_quest(excluded_quest, user_id)
        
        return manager

    def add_excluded_quest(self, quest_data: Any, user_id: str = '') -> None:
        """Add an excluded quest to the manager.
        
        Args:
            quest_data: Quest data
            user_id: User ID for context
        """
        try:
            quest = Quest(quest_data)
            self._quests[quest.id] = quest
        except (ValueError, KeyError):
            pass

    def __iter__(self) -> Iterator[Quest]:
        """Iterate over quests."""
        return iter(self._quests.values())

    def __len__(self) -> int:
        """Get number of quests."""
        return len(self._quests)

    @property
    def size(self) -> int:
        """Get number of quests."""
        return len(self._quests)

    def list(self) -> List[Quest]:
        """Get list of all quests."""
        return list(self._quests.values())

    def get(self, quest_id: str) -> Optional[Quest]:
        """Get quest by ID.
        
        Args:
            quest_id: Quest ID
            
        Returns:
            Quest if found, None otherwise
        """
        return self._quests.get(quest_id)

    def upsert(self, quest: Quest) -> None:
        """Insert or update quest.
        
        Args:
            quest: Quest to insert or update
        """
        self._quests[quest.id] = quest

    def remove(self, quest_id: str) -> bool:
        """Remove quest by ID.
        
        Args:
            quest_id: Quest ID
            
        Returns:
            True if removed, False if not found
        """
        return self._quests.pop(quest_id, None) is not None

    def clear(self) -> None:
        """Clear all quests."""
        self._quests.clear()

    def get_expired(self, date: Optional[datetime] = None) -> List[Quest]:
        """Get all expired quests.
        
        Args:
            date: Reference date (default: now)
            
        Returns:
            List of expired quests
        """
        if date is None:
            date = datetime.now()
        return [q for q in self._quests.values() if q.is_expired(date)]

    def get_active(self) -> List[Quest]:
        """Get all non-expired quests."""
        return [q for q in self._quests.values() if not q.is_expired()]

    def get_available(self) -> List[Quest]:
        """Get all quests available for enrollment."""
        return [q for q in self._quests.values() if not q.is_enrolled() and not q.is_expired()]

    def get_enrolled(self) -> List[Quest]:
        """Get all enrolled quests."""
        return [q for q in self._quests.values() if q.is_enrolled() and not q.is_completed()]

    def get_completed(self) -> List[Quest]:
        """Get all completed quests."""
        return [q for q in self._quests.values() if q.is_completed() and not q.has_claimed_rewards()]

    def get_claimable(self) -> List[Quest]:
        """Get all quests with claimable rewards."""
        return [q for q in self._quests.values() if q.is_completed() and not q.has_claimed_rewards()]

    def __repr__(self) -> str:
        """String representation."""
        return f"<QuestManager with {len(self._quests)} quests>"
