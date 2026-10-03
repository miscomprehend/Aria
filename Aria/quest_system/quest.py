"""Quest wrapper class."""

from typing import Optional, Dict, Any
from datetime import datetime
from .interface import Quest as QuestData, QuestUserStatus


class Quest:
    """Wrapper around quest data with convenience methods."""

    def __init__(self, data: QuestData):
        """Initialize quest wrapper.
        
        Args:
            data: Quest data from API
        """
        self._data = data

    @classmethod
    def create(cls, data: Dict[str, Any], user_id: str = '') -> 'Quest':
        """Create Quest from API response data."""
        quest_data = QuestData.from_dict(data, user_id)
        return cls(quest_data)

    @property
    def id(self) -> str:
        """Quest ID."""
        return self._data.id

    @property
    def config(self) -> Any:
        """Quest configuration."""
        return self._data.config

    @property
    def user_status(self) -> Optional[QuestUserStatus]:
        """User's status on this quest."""
        return self._data.user_status

    @property
    def targeted_content(self) -> int:
        """Targeted content."""
        return self._data.targeted_content

    @property
    def preview(self) -> bool:
        """Whether this is a preview quest."""
        return self._data.preview

    @property
    def raw(self) -> QuestData:
        """Raw quest data."""
        return self._data

    def is_expired(self, reference: Optional[datetime] = None) -> bool:
        """Check if quest is expired."""
        return self._data.is_expired(reference)

    def is_completed(self) -> bool:
        """Check if quest is completed."""
        return self._data.is_completed()

    def is_enrolled(self) -> bool:
        """Check if user is enrolled in this quest."""
        return self._data.is_enrolled()

    def has_claimed_rewards(self) -> bool:
        """Check if rewards have been claimed."""
        return self._data.has_claimed_rewards()

    def update_user_status(self, user_status: Optional[QuestUserStatus]) -> None:
        """Update user status."""
        self._data.user_status = user_status

    def __repr__(self) -> str:
        """String representation."""
        name = 'Unknown Quest'
        if self.config and self.config.messages:
            name = self.config.messages.quest_name
        state = self.get_state()
        return f"<Quest {self.id[:8]}... '{name}' [{state}]>"

    def get_state(self) -> str:
        """Get current quest state."""
        if self.is_expired():
            return "Expired"
        if self.is_completed():
            if self.has_claimed_rewards():
                return "Reward Claimed"
            return "Completed"
        if self.is_enrolled():
            return "In Progress"
        return "Available"
