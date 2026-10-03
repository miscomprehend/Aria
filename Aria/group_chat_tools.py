"""Explicit, one-at-a-time group-DM utilities for Aria's command runtime."""

from __future__ import annotations

import base64
import re
from typing import Any, Callable
from urllib.parse import urlsplit


_USER_ID_RE = re.compile(r"^\d{1,20}$")
_MAX_ICON_BYTES = 8 * 1024 * 1024
_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


class GroupChatTools:
    def __init__(self, api: Any):
        self.api = api

    def _group(self, channel_id: str) -> tuple[dict | None, str | None]:
        channel_id = str(channel_id or "")
        if not channel_id.isdigit():
            return None, "This command needs a group-DM channel."
        response = self.api.request("GET", f"/channels/{channel_id}")
        if response is None or response.status_code != 200:
            return None, f"Could not load group-DM details (HTTP {getattr(response, 'status_code', 'no response')})."
        data = response.json()
        if not isinstance(data, dict) or data.get("type") != 3:
            return None, "This command only works in a group DM."
        return data, None

    def get_icon(self, channel_id: str) -> str:
        data, error = self._group(channel_id)
        if error:
            return error
        icon = data.get("icon")
        if not icon:
            return "This group DM has no icon set."
        return f"Group-DM icon: https://cdn.discordapp.com/channel-icons/{channel_id}/{icon}.png?size=4096"

    def set_icon(self, channel_id: str, url: str) -> str:
        data, error = self._group(channel_id)
        if error:
            return error
        parsed = urlsplit(str(url or "").strip())
        if parsed.scheme != "https" or not parsed.netloc:
            return "Provide a valid HTTPS image URL."
        try:
            import requests
            with requests.get(url, timeout=10, stream=True) as response:
                response.raise_for_status()
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if mime not in _IMAGE_MIME_TYPES:
                    return "The URL must return a PNG, JPEG, GIF, or WebP image."
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > _MAX_ICON_BYTES:
                    return "The image must be 8 MiB or smaller."
                image = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    image.extend(chunk)
                    if len(image) > _MAX_ICON_BYTES:
                        return "The image must be 8 MiB or smaller."
            if not image:
                return "The image URL returned an empty file."
            encoded = base64.b64encode(image).decode("ascii")
            data_uri = f"data:{mime};base64,{encoded}"
            updated = self.api.request(
                "PATCH", f"/channels/{channel_id}", data={"icon": data_uri}
            )
            if updated is not None and updated.status_code in (200, 204):
                return "Group-DM icon updated."
            return f"Icon update failed (HTTP {getattr(updated, 'status_code', 'no response')})."
        except Exception as exc:
            return f"Icon update failed: {exc}"

    def change_member(self, channel_id: str, user_value: str, add: bool) -> str:
        data, error = self._group(channel_id)
        if error:
            return error
        user_id = str(user_value or "").strip().strip("<@!>")
        if not _USER_ID_RE.fullmatch(user_id):
            return "Provide a numeric user ID or mention."
        recipients = data.get("recipients") or []
        is_member = any(str(user.get("id") or "") == user_id for user in recipients)
        if add and is_member:
            return f"User {user_id} is already in this group DM."
        if not add and not is_member:
            return f"User {user_id} is not in this group DM."
        method = "PUT" if add else "DELETE"
        response = self.api.request(
            method,
            f"/channels/{channel_id}/recipients/{user_id}",
            data={} if add else None,
        )
        success_codes = (200, 201, 204)
        if response is not None and response.status_code in success_codes:
            return f"{'Added' if add else 'Removed'} {user_id} {'to' if add else 'from'} this group DM."
        return f"Member update failed (HTTP {getattr(response, 'status_code', 'no response')})."


def setup_group_chat_tools(bot: Any, is_control_user: Callable[[str], bool]) -> GroupChatTools:
    tools = GroupChatTools(bot.api)
    bot.group_chat_tools = tools

    def _send(ctx: dict, text: str) -> None:
        ctx["api"].send_message(ctx["channel_id"], f"> **Group DM** :: {text}")

    def _run(ctx: dict, operation: Callable[[], str]) -> None:
        if not is_control_user(str(ctx.get("author_id") or "")):
            _send(ctx, "Owner/Admin only.")
            return
        try:
            _send(ctx, operation())
        except Exception as exc:
            _send(ctx, f"Operation failed: {exc}")

    @bot.command(name="gcicon")
    def gcicon_cmd(ctx, args):
        _run(ctx, lambda: tools.get_icon(str(ctx.get("channel_id") or "")))

    @bot.command(name="setgcicon")
    def setgcicon_cmd(ctx, args):
        url = " ".join(args).strip()
        if not url:
            _send(ctx, f"Usage: {bot.prefix}setgcicon <https_image_url>")
            return
        _run(ctx, lambda: tools.set_icon(str(ctx.get("channel_id") or ""), url))

    @bot.command(name="gcadd")
    def gcadd_cmd(ctx, args):
        _run(ctx, lambda: tools.change_member(
            str(ctx.get("channel_id") or ""), args[0] if args else "", True
        ))

    @bot.command(name="gcremove")
    def gcremove_cmd(ctx, args):
        _run(ctx, lambda: tools.change_member(
            str(ctx.get("channel_id") or ""), args[0] if args else "", False
        ))

    return tools
