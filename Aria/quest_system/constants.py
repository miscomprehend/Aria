"""Quest system constants."""

import uuid
import json
import base64

class Constants:
    """Discord constants for quest system."""

    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9236 Chrome/138.0.7204.251 Electron/37.6.0 Safari/537.36'
    ANDROID_USER_AGENT = 'Discord-Android/316011;RNA'

    # Desktop properties
    PROPERTIES = {
        'os': 'Windows',
        'browser': 'Discord Client',
        'release_channel': 'stable',
        'client_version': '1.0.9236',
        'os_version': '10.0.19045',
        'os_arch': 'x64',
        'app_arch': 'x64',
        'system_locale': 'en-US',
        'has_client_mods': False,
        'client_launch_id': str(uuid.uuid4()),
        'browser_user_agent': USER_AGENT,
        'browser_version': '37.6.0',
        'os_sdk_version': '19045',
        'client_build_number': 539951,
        'native_build_number': 81687,
        'client_event_source': None,
        'launch_signature': str(uuid.uuid4()),
        'client_heartbeat_session_id': str(uuid.uuid4()),
        'client_app_state': 'focused',
    }

    # Android properties
    ANDROID_PROPERTIES = {
        'os': 'Android',
        'browser': 'Discord Android',
        'device': 'b0q',
        'system_locale': 'en-US',
        'has_client_mods': False,
        'client_version': '316.11 - rn',
        'release_channel': 'googleRelease',
        'device_vendor_id': str(uuid.uuid4()),
        'design_id': 2,
        'browser_user_agent': '',
        'browser_version': '',
        'os_version': '28',
        'client_build_number': 5169,
        'client_event_source': None,
        'client_launch_id': str(uuid.uuid4()),
        'launch_signature': '1771754995045142953',
        'client_app_state': 'active',
        'client_heartbeat_session_id': str(uuid.uuid4()),
    }

    @staticmethod
    def get_super_properties_header(is_android: bool = False) -> str:
        """Get base64 encoded super properties header."""
        props = Constants.ANDROID_PROPERTIES if is_android else Constants.PROPERTIES
        json_props = json.dumps(props)
        return base64.b64encode(json_props.encode()).decode()
