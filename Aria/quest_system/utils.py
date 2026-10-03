"""Utility functions for quest system."""

import base64
import json
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
from urllib.parse import urlencode, quote
from .constants import Constants


class Utils:
    """Utility functions for quest operations."""

    @staticmethod
    def make_headers(
        token: str,
        base_headers: Optional[Dict[str, str]] = None,
        is_android: bool = False,
        with_origin: bool = True,
    ) -> Dict[str, str]:
        """Create Discord headers for quest API requests.
        
        Args:
            token: Discord token (without "Bot " prefix)
            base_headers: Base headers to extend
            is_android: Whether to use Android headers
            with_origin: Whether to include origin/referer
            
        Returns:
            Headers dictionary
        """
        headers = dict(base_headers or {})
        
        # Remove Bot prefix if present
        if token.startswith('Bot '):
            token = token[4:]
        
        headers['Authorization'] = token
        headers['Accept-Language'] = 'en-US'
        headers['X-Debug-Options'] = 'bugReporterEnabled'
        headers['X-Discord-Locale'] = 'en-US'
        headers['X-Discord-Timezone'] = 'America/New_York'
        
        if is_android:
            headers.update(Utils._make_android_headers(with_origin))
        else:
            headers.update(Utils._make_desktop_headers(with_origin))
        
        return headers

    @staticmethod
    def _make_desktop_headers(with_origin: bool = True) -> Dict[str, str]:
        """Create desktop user headers."""
        headers = {
            'Accept-Language': 'en-US',
            'User-Agent': Constants.USER_AGENT,
            'Pragma': 'no-cache',
            'Priority': 'u=1, i',
            'Sec-CH-UA': '"Not)A;Brand";v="8", "Chromium";v="138"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Super-Properties': Constants.get_super_properties_header(False),
        }
        
        if with_origin:
            headers['Origin'] = 'https://discord.com'
            headers['Referer'] = 'https://discord.com/channels/@me'
        
        return headers

    @staticmethod
    def _make_android_headers(with_origin: bool = True) -> Dict[str, str]:
        """Create Android user headers."""
        headers = {
            'Accept-Language': 'en-US',
            'User-Agent': Constants.ANDROID_USER_AGENT,
            'X-Super-Properties': Constants.get_super_properties_header(True),
        }
        
        if with_origin:
            headers['Origin'] = 'https://discord.com'
            headers['Referer'] = 'https://discord.com/channels/@me'
        
        return headers

    @staticmethod
    def merge_headers(base: Dict[str, str], additional: Dict[str, str]) -> Dict[str, str]:
        """Merge two header dictionaries."""
        result = dict(base)
        result.update(additional)
        return result

    @staticmethod
    def get_proxy_ticket(
        application_id: str,
        rest_api: Any,
    ) -> str:
        """Get a proxy ticket for Discord Says activities.
        
        Args:
            application_id: Application ID
            rest_api: REST API client
            
        Returns:
            Proxy ticket string
        """
        endpoint = f'/applications/{application_id}/proxy-tickets'
        response = rest_api.post(endpoint, json={})
        if response and 'ticket' in response:
            return response['ticket']
        raise ValueError(f"Failed to get proxy ticket for {application_id}")

    @staticmethod
    def get_activity_referrer(
        application_id: str,
        proxy_ticket: str,
    ) -> str:
        """Get referrer URL for Discord Says activity.
        
        Args:
            application_id: Application ID
            proxy_ticket: Proxy ticket
            
        Returns:
            Referrer URL
        """
        base_url = f'https://{application_id}.discordsays.com/'
        params = {
            'instance_id': 'example-cl-instance',
            'platform': 'desktop',
            'discord_proxy_ticket': proxy_ticket,
        }
        return base_url + '?' + urlencode(params)

    @staticmethod
    def get_activity_headers(
        quest_id: str,
        auth_token: str = '',
        activity_referrer: Optional[str] = None,
    ) -> Dict[str, str]:
        """Get headers for Discord Says activity requests.
        
        Args:
            quest_id: Quest ID
            auth_token: Auth token for the activity
            activity_referrer: Referrer URL
            
        Returns:
            Headers dictionary
        """
        headers = {
            'Content-Type': 'application/json',
            'X-Auth-Token': auth_token,
            'X-Discord-Quest-ID': quest_id,
        }
        
        if activity_referrer:
            headers['Referer'] = activity_referrer
        
        return headers

    @staticmethod
    def extract_heartbeat_payload(quest_type: str, quest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract heartbeat payload based on quest type.
        
        Args:
            quest_type: Type of quest (watch, play, stream)
            quest_data: Quest data
            
        Returns:
            Payload dictionary
        """
        payload = {}
        
        config = quest_data.get('config', {})
        application = config.get('application', {})
        
        if application and application.get('id'):
            payload['application_id'] = application['id']
        
        return payload

    @staticmethod
    def extract_video_progress_payload(
        current_progress: float,
        max_progress: float,
    ) -> Dict[str, Any]:
        """Extract video progress payload.
        
        Args:
            current_progress: Current progress value
            max_progress: Maximum progress value
            
        Returns:
            Payload dictionary
        """
        # Discord accepts various payload formats for video progress
        return {
            'timestamp': current_progress,
            'value': current_progress,
            'seconds': current_progress,
        }

    @staticmethod
    def parse_quest_progress(response: Dict[str, Any]) -> Tuple[int, bool]:
        """Parse progress from API response.
        
        Args:
            response: API response
            
        Returns:
            Tuple of (progress_value, is_completed)
        """
        progress = 0
        completed = False
        
        # Check for completed marker
        if response.get('completed_at'):
            completed = True
        
        # Extract progress value
        if response.get('progress'):
            for event_data in response['progress'].values():
                if isinstance(event_data, dict):
                    try:
                        value = int(float(event_data.get('value', 0)))
                        progress = max(progress, value)
                    except (ValueError, TypeError):
                        pass
        
        # Check stream progress
        if response.get('streamProgressSeconds'):
            try:
                sps = int(float(response['streamProgressSeconds']))
                progress = max(progress, sps)
            except (ValueError, TypeError):
                pass
        
        return progress, completed

    @staticmethod
    def is_expired(iso_date: Optional[str]) -> bool:
        """Check if an ISO date is in the past.
        
        Args:
            iso_date: ISO format date string
            
        Returns:
            True if expired
        """
        if not iso_date:
            return False
        
        try:
            expires = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return datetime.now() > expires
        except (ValueError, TypeError):
            return False

    @staticmethod
    def get_quest_display_name(quest_data: Dict[str, Any]) -> str:
        """Get human-readable quest name.
        
        Args:
            quest_data: Quest data
            
        Returns:
            Quest name
        """
        config = quest_data.get('config', {})
        if not isinstance(config, dict):
            return 'Unknown Quest'
        
        # Check video quest title first
        video_metadata = config.get('video_metadata', {})
        if isinstance(video_metadata, dict):
            messages = video_metadata.get('messages', {})
            if isinstance(messages, dict):
                title = messages.get('video_title')
                if title:
                    return str(title)
        
        # Fall back to quest name
        messages = config.get('messages', {})
        if isinstance(messages, dict):
            name = messages.get('quest_name') or messages.get('game_title')
            if name:
                return str(name)
        
        # Fall back to application name
        application = config.get('application', {})
        if isinstance(application, dict):
            app_name = application.get('name')
            if app_name:
                return f"Quest by {app_name}"
        
        return 'Unknown Quest'

    @staticmethod
    def get_task_type(quest_data: Dict[str, Any]) -> str:
        """Determine quest task type.
        
        Args:
            quest_data: Quest data
            
        Returns:
            Task type string (watch, play, stream, unknown)
        """
        config = quest_data.get('config', {})
        if not isinstance(config, dict):
            return 'unknown'
        
        task_config = config.get('task_config_v2', {})
        if not isinstance(task_config, dict):
            return 'unknown'
        
        tasks = task_config.get('tasks', {})
        if not isinstance(tasks, dict):
            return 'unknown'
        
        task_keys = ' '.join(tasks.keys()).lower()
        
        if any(x in task_keys for x in ['watch', 'video']):
            return 'watch'
        if any(x in task_keys for x in ['play', 'gaming']):
            return 'play'
        if 'stream' in task_keys:
            return 'stream'
        
        return 'unknown'
