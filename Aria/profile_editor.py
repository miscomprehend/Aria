"""Read and update the signed-in Discord account's profile for the dashboard.

Mirrors the bot's profile commands (setpfp, setbanner, setname, setbio,
setpronouns, setaccent) so the dashboard Account tab and the commands behave
the same way.
"""

import base64
import binascii
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from profile_avatar import MAX_AVATAR_BYTES, download_avatar_data_uri, image_to_data_uri

MAX_DISPLAY_NAME = 32
MAX_BIO = 190
MAX_PRONOUNS = 40

# base64 inflates by 4/3; reject oversized strings before decoding them.
_MAX_ENCODED_IMAGE = (MAX_AVATAR_BYTES * 4) // 3 + 1024
_HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})$")

_ACCOUNT_FIELDS = ("avatar", "banner", "global_name", "accent_color")
_PROFILE_FIELDS = ("bio", "pronouns")


class ProfileError(ValueError):
    """A request problem that is safe to show to the user."""


def _cdn_url(kind: str, user_id: str, image_hash: Any, size: int) -> str:
    image_hash = str(image_hash or "").strip()
    if not user_id or not image_hash:
        return ""
    extension = "gif" if image_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/{kind}/{user_id}/{image_hash}.{extension}?size={size}"


def fetch_profile(api) -> Dict[str, Any]:
    """Return the account's current editable profile."""
    account_response = api.request("GET", "/users/@me")
    status = getattr(account_response, "status_code", None)
    if account_response is None or status != 200:
        raise ProfileError(f"Could not load the account profile (HTTP {status or 'no response'}).")
    account = account_response.json() or {}

    profile: Dict[str, Any] = {}
    profile_response = api.request("GET", "/users/@me/profile")
    if profile_response is not None and getattr(profile_response, "status_code", None) == 200:
        payload = profile_response.json() or {}
        profile = payload.get("user_profile") or {}

    primary_guild = account.get("primary_guild")
    primary_guild = primary_guild if isinstance(primary_guild, dict) else {}
    connections_response = api.request("GET", "/users/@me/connections")
    connections = []
    if connections_response is not None and getattr(connections_response, "status_code", None) == 200:
        response_connections = connections_response.json()
        if isinstance(response_connections, list):
            seen_platforms = set()
            for connection in response_connections:
                if not isinstance(connection, dict):
                    continue
                platform = str(connection.get("type") or "").strip().lower()
                if platform and platform not in seen_platforms:
                    connections.append(platform)
                    seen_platforms.add(platform)

    user_id = str(account.get("id") or "")
    accent = account.get("accent_color")
    return {
        "user_id": user_id,
        "username": account.get("username") or "",
        "global_name": account.get("global_name") or "",
        "avatar_url": _cdn_url("avatars", user_id, account.get("avatar"), 256),
        "banner_url": _cdn_url("banners", user_id, account.get("banner"), 600),
        "accent_color": f"#{accent:06x}" if isinstance(accent, int) else "",
        "bio": str(profile.get("bio") or ""),
        "pronouns": str(profile.get("pronouns") or ""),
        "guild_tag": str(primary_guild.get("tag") or "") if primary_guild.get("identity_enabled") else "",
        "connected_platforms": connections,
        "premium_type": int(account.get("premium_type") or 0),
        "limits": {"global_name": MAX_DISPLAY_NAME, "bio": MAX_BIO, "pronouns": MAX_PRONOUNS},
    }


def _text_field(payload: Dict[str, Any], key: str, limit: int, label: str) -> str:
    value = payload[key]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProfileError(f"{label} must be text.")
    value = value.strip()
    if len(value) > limit:
        raise ProfileError(f"{label} must be {limit} characters or fewer.")
    return value


def _image_field(spec: Any, label: str) -> Optional[str]:
    """Turn an image request into a data URI, or None to remove the image."""
    if spec is None or (isinstance(spec, dict) and spec.get("remove")):
        return None
    if not isinstance(spec, dict):
        raise ProfileError(f"{label} must be an object with 'url', 'data' or 'remove'.")

    url = spec.get("url")
    if isinstance(url, str) and url.strip():
        try:
            return download_avatar_data_uri(url)
        except ValueError as exc:
            raise ProfileError(f"{label}: {exc}") from exc

    data = spec.get("data")
    if not isinstance(data, str) or not data.strip():
        raise ProfileError(f"{label} needs an image URL or an uploaded file.")
    data = data.strip()
    if data.startswith("data:"):
        _, _, data = data.partition(",")
    if len(data) > _MAX_ENCODED_IMAGE:
        raise ProfileError(f"{label} exceeds the 10 MiB size limit.")
    try:
        raw = base64.b64decode(data, validate=True)
        return image_to_data_uri(raw)
    except (binascii.Error, ValueError) as exc:
        raise ProfileError(f"{label}: {exc}") from exc


def parse_update(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Validate a dashboard request into (account_patch, profile_patch).

    Only keys present in ``payload`` are changed.
    """
    if not isinstance(payload, dict):
        raise ProfileError("Expected a JSON object.")

    account: Dict[str, Any] = {}
    profile: Dict[str, Any] = {}

    if "global_name" in payload:
        name = _text_field(payload, "global_name", MAX_DISPLAY_NAME, "Display name")
        account["global_name"] = name or None
    if "accent_color" in payload:
        raw = payload["accent_color"]
        if raw in (None, ""):
            account["accent_color"] = None
        else:
            match = _HEX_COLOR.match(str(raw).strip())
            if not match:
                raise ProfileError("Accent color must be a hex color such as #5b8cff.")
            account["accent_color"] = int(match.group(1), 16)
    if "avatar" in payload:
        account["avatar"] = _image_field(payload["avatar"], "Profile picture")
    if "banner" in payload:
        account["banner"] = _image_field(payload["banner"], "Banner")
    if "bio" in payload:
        profile["bio"] = _text_field(payload, "bio", MAX_BIO, "Bio")
    if "pronouns" in payload:
        profile["pronouns"] = _text_field(payload, "pronouns", MAX_PRONOUNS, "Pronouns")

    if not account and not profile:
        raise ProfileError("Nothing to update.")
    return account, profile


def _error_detail(response) -> str:
    """Pull a readable message out of a Discord error body."""
    try:
        body = response.json()
    except Exception:
        return ""
    if not isinstance(body, dict):
        return ""

    def first_message(node) -> str:
        if isinstance(node, dict):
            errors = node.get("_errors")
            if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                return str(errors[0].get("message") or "")
            for value in node.values():
                found = first_message(value)
                if found:
                    return found
        return ""

    return first_message(body.get("errors")) or str(body.get("message") or "")


def _patch(api, endpoint: str, patch: Dict[str, Any], attempts: int = 3) -> Tuple[bool, str]:
    detail = "Request failed"
    for attempt in range(attempts):
        try:
            response = api.request("PATCH", endpoint, data=patch)
        except Exception as exc:
            detail = str(exc)[:120] or detail
            response = None
        status = getattr(response, "status_code", None)
        if status in (200, 201, 204):
            return True, ""
        if response is not None:
            detail = _error_detail(response) or f"HTTP {status}"
        retryable = status is None or status == 429 or status >= 500
        if attempt + 1 >= attempts or not retryable:
            break
        wait = 0.75
        if status == 429:
            try:
                wait = min(5.0, float((response.json() or {}).get("retry_after", 1.0)))
            except Exception:
                wait = 1.0
        time.sleep(wait)
    return False, detail


def apply_update(api, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a validated update; account and profile fields are patched independently."""
    account_patch, profile_patch = parse_update(payload)
    updated: List[str] = []
    failed: List[Dict[str, Any]] = []

    for endpoint, patch in (("/users/@me", account_patch), ("/users/@me/profile", profile_patch)):
        if not patch:
            continue
        ok, detail = _patch(api, endpoint, patch)
        if ok:
            updated.extend(patch)
        else:
            failed.append({"fields": list(patch), "error": detail})
    return {"updated": updated, "failed": failed}
