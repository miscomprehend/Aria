"""Quest system interfaces and data classes."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class QuestAssets:
    """Quest asset configuration."""
    hero_banner_url: Optional[str] = None
    hero_banner_dark_url: Optional[str] = None
    hero_video_url: Optional[str] = None
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    card_banner_url: Optional[str] = None
    card_banner_dark_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestAssets':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            hero_banner_url=data.get('hero_banner_url'),
            hero_banner_dark_url=data.get('hero_banner_dark_url'),
            hero_video_url=data.get('hero_video_url'),
            logo_url=data.get('logo_url'),
            logo_dark_url=data.get('logo_dark_url'),
            card_banner_url=data.get('card_banner_url'),
            card_banner_dark_url=data.get('card_banner_dark_url'),
        )


@dataclass
class QuestApplication:
    """Application metadata for quest."""
    id: str
    name: str
    icon: Optional[str] = None
    splash: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestApplication':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls(id='', name='Unknown')
        return cls(
            id=data.get('id', ''),
            name=data.get('name', 'Unknown'),
            icon=data.get('icon'),
            splash=data.get('splash'),
        )


@dataclass
class QuestGradient:
    """Quest gradient/color configuration."""
    primary_color: Optional[str] = None
    primary_dark_color: Optional[str] = None
    secondary_color: Optional[str] = None
    tertiary_color: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestGradient':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            primary_color=data.get('primary_color'),
            primary_dark_color=data.get('primary_dark_color'),
            secondary_color=data.get('secondary_color'),
            tertiary_color=data.get('tertiary_color'),
        )


@dataclass
class QuestMessages:
    """Human-readable quest messages."""
    quest_name: str
    game_title: Optional[str] = None
    game_description: Optional[str] = None
    quest_description: Optional[str] = None
    task_description: Optional[str] = None
    task_description_mobile: Optional[str] = None
    reward_description: Optional[str] = None
    reward_notice: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestMessages':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls(quest_name='Unknown Quest')
        return cls(
            quest_name=data.get('quest_name', 'Unknown Quest'),
            game_title=data.get('game_title'),
            game_description=data.get('game_description'),
            quest_description=data.get('quest_description'),
            task_description=data.get('task_description'),
            task_description_mobile=data.get('task_description_mobile'),
            reward_description=data.get('reward_description'),
            reward_notice=data.get('reward_notice'),
        )


@dataclass
class QuestRewardsConfig:
    """Rewards configuration for quest."""
    rewards: List[Dict[str, Any]] = field(default_factory=list)
    rewards_expire_at: Optional[str] = None
    assignment_method: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestRewardsConfig':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            rewards=data.get('rewards', []) or [],
            rewards_expire_at=data.get('rewards_expire_at'),
            assignment_method=data.get('assignment_method'),
        )


@dataclass
class QuestVideoMetadata:
    """Video quest metadata."""
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    video_description: Optional[str] = None
    duration_seconds: Optional[int] = None
    short_link: Optional[str] = None
    messages: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestVideoMetadata':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            video_url=data.get('video_url'),
            video_title=data.get('video_title'),
            video_description=data.get('video_description'),
            duration_seconds=data.get('duration_seconds'),
            short_link=data.get('short_link'),
            messages=data.get('messages', {}),
        )


@dataclass
class QuestCosponsorMetadata:
    """Co-sponsor quest metadata."""
    cosponsor_id: Optional[str] = None
    cosponsor_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestCosponsorMetadata':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            cosponsor_id=data.get('cosponsor_id'),
            cosponsor_name=data.get('cosponsor_name'),
        )


@dataclass
class QuestTaskProgress:
    """User's progress on a single task."""
    event_name: str
    value: int = 0
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestTaskProgress':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls(event_name='unknown')
        return cls(
            event_name=data.get('event_name', 'unknown'),
            value=int(data.get('value', 0)) if data.get('value') else 0,
            updated_at=data.get('updated_at'),
        )


@dataclass
class QuestUserStatus:
    """User's status/progress on a quest."""
    user_id: str
    quest_id: Optional[str] = None
    enrolled_at: Optional[str] = None
    completed_at: Optional[str] = None
    claimed_at: Optional[str] = None
    claimed_tier: Optional[int] = None
    last_stream_heartbeat_at: Optional[str] = None
    stream_progress_seconds: Optional[str] = None
    dismissed_quest_content: Optional[int] = None
    progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], user_id: str) -> 'QuestUserStatus':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls(user_id=user_id)
        
        progress_dict = {}
        progress_raw = data.get('progress', {})
        if isinstance(progress_raw, dict):
            for key, val in progress_raw.items():
                if isinstance(val, dict):
                    progress_dict[key] = val
        
        return cls(
            user_id=user_id,
            quest_id=data.get('quest_id'),
            enrolled_at=data.get('enrolled_at'),
            completed_at=data.get('completed_at'),
            claimed_at=data.get('claimed_at'),
            claimed_tier=data.get('claimed_tier'),
            last_stream_heartbeat_at=data.get('last_stream_heartbeat_at'),
            stream_progress_seconds=data.get('stream_progress_seconds'),
            dismissed_quest_content=data.get('dismissed_quest_content'),
            progress=progress_dict,
        )


@dataclass
class QuestConfig:
    """Quest configuration."""
    id: str
    config_version: int
    starts_at: str
    expires_at: str
    features: int
    application: QuestApplication
    assets: Optional[QuestAssets] = None
    colors: Optional[QuestGradient] = None
    messages: Optional[QuestMessages] = None
    rewards_config: Optional[QuestRewardsConfig] = None
    video_metadata: Optional[QuestVideoMetadata] = None
    cosponsor_metadata: Optional[QuestCosponsorMetadata] = None
    task_config_v2: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QuestConfig':
        """Create from API response."""
        if not isinstance(data, dict):
            raise ValueError("Quest config must be a dictionary")
        
        return cls(
            id=data.get('id', ''),
            config_version=data.get('config_version', 1),
            starts_at=data.get('starts_at', ''),
            expires_at=data.get('expires_at', ''),
            features=data.get('features', 0),
            application=QuestApplication.from_dict(data.get('application', {})),
            assets=QuestAssets.from_dict(data.get('assets', {})),
            colors=QuestGradient.from_dict(data.get('colors', {})),
            messages=QuestMessages.from_dict(data.get('messages', {})),
            rewards_config=QuestRewardsConfig.from_dict(data.get('rewards_config', {})),
            video_metadata=QuestVideoMetadata.from_dict(data.get('video_metadata')),
            cosponsor_metadata=QuestCosponsorMetadata.from_dict(data.get('cosponsor_metadata')),
            task_config_v2=data.get('task_config_v2', {}),
        )


@dataclass
class Quest:
    """Discord quest representation."""
    id: str
    config: QuestConfig
    user_status: Optional[QuestUserStatus] = None
    targeted_content: int = 0
    preview: bool = False
    traffic_metadata_raw: Optional[str] = None
    traffic_metadata_sealed: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], user_id: str = '') -> 'Quest':
        """Create from API response."""
        if not isinstance(data, dict):
            raise ValueError("Quest data must be a dictionary")
        
        quest_id = data.get('id', '')
        user_status = None
        if data.get('user_status'):
            user_status = QuestUserStatus.from_dict(data['user_status'], user_id)
        
        return cls(
            id=quest_id,
            config=QuestConfig.from_dict(data.get('config', {})),
            user_status=user_status,
            targeted_content=data.get('targeted_content', 0),
            preview=data.get('preview', False),
            traffic_metadata_raw=data.get('traffic_metadata_raw'),
            traffic_metadata_sealed=data.get('traffic_metadata_sealed'),
        )

    def is_expired(self, reference_date: Optional[datetime] = None) -> bool:
        """Check if quest is expired."""
        from datetime import timezone
        
        if reference_date is None:
            reference_date = datetime.now(timezone.utc)
        
        try:
            # Ensure reference_date is timezone-aware
            if reference_date.tzinfo is None:
                reference_date = reference_date.replace(tzinfo=timezone.utc)
            
            expires = datetime.fromisoformat(self.config.expires_at.replace('Z', '+00:00'))
            return reference_date > expires
        except (ValueError, AttributeError):
            return False

    def is_completed(self) -> bool:
        """Check if quest is completed."""
        return bool(self.user_status and self.user_status.completed_at)

    def is_enrolled(self) -> bool:
        """Check if quest is enrolled."""
        return bool(self.user_status and self.user_status.enrolled_at)

    def has_claimed_rewards(self) -> bool:
        """Check if rewards have been claimed."""
        return bool(self.user_status and self.user_status.claimed_at)


@dataclass
class AllQuestsResponse:
    """API response for all quests."""
    quests: List[Quest] = field(default_factory=list)
    excluded_quests: List[Quest] = field(default_factory=list)
    quest_enrollment_blocked_until: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], user_id: str = '') -> 'AllQuestsResponse':
        """Create from API response."""
        if not isinstance(data, dict):
            return cls()
        
        quests = []
        for quest_data in data.get('quests', []) or []:
            try:
                quests.append(Quest.from_dict(quest_data, user_id))
            except (ValueError, KeyError):
                continue
        
        excluded = []
        for quest_data in data.get('excluded_quests', []) or []:
            try:
                excluded.append(Quest.from_dict(quest_data, user_id))
            except (ValueError, KeyError):
                continue
        
        return cls(
            quests=quests,
            excluded_quests=excluded,
            quest_enrollment_blocked_until=data.get('quest_enrollment_blocked_until'),
        )


class QuestTaskConfigType:
    """Quest task configuration type enumeration."""
    WATCH_VIDEO = "WATCH_VIDEO"
    WATCH_VIDEO_ON_MOBILE = "WATCH_VIDEO_ON_MOBILE"
    PLAY_ON_DESKTOP = "PLAY_ON_DESKTOP"
    PLAY_ON_XBOX = "PLAY_ON_XBOX"
    PLAY_ON_PLAYSTATION = "PLAY_ON_PLAYSTATION"
    PLAY_ACTIVITY = "PLAY_ACTIVITY"
    ACHIEVEMENT_IN_ACTIVITY = "ACHIEVEMENT_IN_ACTIVITY"


class CaptchaDataFromRequest:
    """Data from captcha challenge."""
    def __init__(self, captcha_sitekey: str, captcha_rqdata: str):
        self.captcha_sitekey = captcha_sitekey
        self.captcha_rqdata = captcha_rqdata
