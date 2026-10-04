"""Explicit, one-at-a-time group-DM utilities for Aria's command runtime."""

from __future__ import annotations

import base64
import re
import time
from typing import Any, Callable
from urllib.parse import urlsplit


_USER_ID_RE = re.compile(r"^\d{1,20}$")
_MAX_ICON_BYTES = 8 * 1024 * 1024
_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


class GroupChatTools:
    def __init__(self, api: Any):
        self.api = api
        self.bot = None
        self.lockdown: dict[str, set[str]] = {}
        self.antiadd: dict[str, set[str]] = {}
        self.whitelists: dict[str, set[str]] = {}

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
            response = self.api.request_external("GET", url, timeout=10, stream=True)
            try:
                if response.status_code != 200:
                    return f"Image download failed (HTTP {response.status_code})."
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
            finally:
                response.close()
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
        target = str(user_value or "").strip().strip("<@!>")
        if not target:
            return "Provide a username, numeric user ID, or mention."
        recipients = data.get("recipients") or []
        if _USER_ID_RE.fullmatch(target):
            user_id = target
            display_name = target
        elif add:
            try:
                relationships = self.api.request("GET", "/users/@me/relationships")
                if relationships is None or relationships.status_code != 200:
                    return f"Could not load friends (HTTP {getattr(relationships, 'status_code', 'no response')})."
                friends = relationships.json()
                user = next((
                    (item.get("user") or {}) for item in friends
                    if item.get("type") == 1
                    and str((item.get("user") or {}).get("username") or "").casefold()
                    == target.casefold()
                ), None)
            except Exception as exc:
                return f"Could not load friends: {exc}"
            if not user:
                return f"No friend found with username {target}."
            user_id = str(user.get("id") or "")
            display_name = str(user.get("username") or user_id)
        else:
            user = next((
                item for item in recipients
                if str(item.get("username") or "").casefold() == target.casefold()
            ), None)
            if not user:
                return f"User {target} is not in this group DM."
            user_id = str(user.get("id") or "")
            display_name = str(user.get("username") or user_id)
        if not user_id:
            return "Could not resolve that user to an ID."
        is_member = any(str(user.get("id") or "") == user_id for user in recipients)
        if add and is_member:
            return f"User {display_name} is already in this group DM."
        if not add and not is_member:
            return f"User {display_name} is not in this group DM."
        method = "PUT" if add else "DELETE"
        response = self.api.request(
            method,
            f"/channels/{channel_id}/recipients/{user_id}",
            data={} if add else None,
        )
        success_codes = (200, 201, 204)
        if response is not None and response.status_code in success_codes:
            return f"{'Added' if add else 'Removed'} {display_name} {'to' if add else 'from'} this group DM."
        return f"Member update failed (HTTP {getattr(response, 'status_code', 'no response')})."

    def _member_ids(self, channel_id: str) -> tuple[set[str] | None, str | None]:
        data, error = self._group(channel_id)
        if error:
            return None, error
        return {
            str(member.get("id"))
            for member in data.get("recipients", [])
            if member.get("id") is not None
        }, None

    def set_lockdown(self, channel_id: str, enabled: bool) -> str:
        if enabled:
            members, error = self._member_ids(channel_id)
            if error:
                return error
            self.lockdown[channel_id] = members or set()
            return f"GC lockdown enabled for {len(self.lockdown[channel_id])} members."
        self.lockdown.pop(str(channel_id), None)
        return "GC lockdown disabled."

    def set_antiadd(self, channel_id: str, enabled: bool) -> str:
        if enabled:
            members, error = self._member_ids(channel_id)
            if error:
                return error
            self.antiadd[channel_id] = members or set()
            return f"GC anti-add enabled for {len(self.antiadd[channel_id])} members."
        self.antiadd.pop(str(channel_id), None)
        return "GC anti-add disabled."

    def whitelist(self, channel_id: str, user_value: str, add: bool) -> str:
        _, error = self._group(channel_id)
        if error:
            return error
        user_id = str(user_value or "").strip().strip("<@!>")
        if not _USER_ID_RE.fullmatch(user_id):
            return "Provide a numeric user ID or mention."
        members = self.whitelists.setdefault(str(channel_id), set())
        if add:
            members.add(user_id)
            return f"Whitelisted {user_id} in this group DM."
        if user_id not in members:
            return f"{user_id} is not whitelisted in this group DM."
        members.discard(user_id)
        if not members:
            self.whitelists.pop(str(channel_id), None)
        return f"Removed {user_id} from this group-DM whitelist."

    def on_channel_recipient_remove(self, event: dict, current_user_id: str = "") -> None:
        channel_id = str(event.get("channel_id") or "")
        user_id = str((event.get("user") or {}).get("id") or "")
        if (
            not user_id
            or user_id == str(current_user_id or self.api.user_id or "")
            or user_id in self.whitelists.get(channel_id, set())
            or user_id not in self.lockdown.get(channel_id, set())
        ):
            return
        self.api.request("PUT", f"/channels/{channel_id}/recipients/{user_id}", data={})

    def on_channel_recipient_add(self, event: dict, current_user_id: str = "") -> None:
        channel_id = str(event.get("channel_id") or "")
        user_id = str((event.get("user") or {}).get("id") or "")
        if (
            not user_id
            or user_id == str(current_user_id or self.api.user_id or "")
            or user_id in self.whitelists.get(channel_id, set())
            or user_id in self.antiadd.get(channel_id, set())
        ):
            return
        self.api.request("DELETE", f"/channels/{channel_id}/recipients/{user_id}")

    def remove_all_members(self, channel_id: str, confirm: bool = False) -> str:
        data, error = self._group(channel_id)
        if error:
            return error
        current_user_id = str(
            getattr(self.bot, "user_id", None)
            or getattr(self.api, "user_id", None)
            or ""
        )
        if not current_user_id:
            return "Could not identify the current account; no members were removed."
        members = [
            member for member in (data.get("recipients") or [])
            if str(member.get("id") or "") != current_user_id
        ]
        if not members:
            return "There are no other members to remove."
        if not confirm:
            return f"This will remove {len(members)} members. Run gcremoveall confirm to continue."
        removed = failed = 0
        for index, member in enumerate(members):
            user_id = str(member.get("id") or "")
            try:
                response = self.api.request(
                    "DELETE", f"/channels/{channel_id}/recipients/{user_id}"
                )
                if response is not None and response.status_code in (200, 204):
                    removed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            if index + 1 < len(members):
                time.sleep(0.5)
        return f"Group-DM member removal complete: {removed} removed, {failed} failed."

    def mass_leave(self, confirm: bool = False) -> str:
        try:
            response = self.api.request("GET", "/users/@me/channels")
            if response is None or response.status_code != 200:
                return f"Could not load group chats (HTTP {getattr(response, 'status_code', 'no response')})."
            channels = response.json()
            groups = [
                channel for channel in channels
                if isinstance(channel, dict) and channel.get("type") == 3
            ]
        except Exception as exc:
            return f"Could not load group chats: {exc}"
        if not groups:
            return "There are no group chats to leave."
        if not confirm:
            return f"This will leave {len(groups)} group chats. Run massgcleave confirm to continue."
        left = failed = 0
        for index, channel in enumerate(groups):
            channel_id = str(channel.get("id") or "")
            try:
                result = self.api.request("DELETE", f"/channels/{channel_id}")
                if result is not None and result.status_code in (200, 204):
                    left += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            if index + 1 < len(groups):
                time.sleep(0.8)
        return f"Group-chat leave complete: {left} left, {failed} failed."


def setup_group_chat_tools(bot: Any, is_control_user: Callable[[str], bool]) -> GroupChatTools:
    tools = GroupChatTools(bot.api)
    tools.bot = bot
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

    @bot.command(name="gclockdown", aliases=["gcld"])
    def gclockdown_cmd(ctx, args):
        state = str(args[0] if args else "").lower()
        if state not in {"on", "off"}:
            _send(ctx, f"Usage: {bot.prefix}gclockdown <on|off>")
            return
        _run(ctx, lambda: tools.set_lockdown(
            str(ctx.get("channel_id") or ""), state == "on"
        ))

    @bot.command(name="gcantiadd", aliases=["gcaa"])
    def gcantiadd_cmd(ctx, args):
        state = str(args[0] if args else "").lower()
        if state not in {"on", "off"}:
            _send(ctx, f"Usage: {bot.prefix}gcantiadd <on|off>")
            return
        _run(ctx, lambda: tools.set_antiadd(
            str(ctx.get("channel_id") or ""), state == "on"
        ))

    @bot.command(name="gcwhitelist", aliases=["gcwl"])
    def gcwhitelist_cmd(ctx, args):
        _run(ctx, lambda: tools.whitelist(
            str(ctx.get("channel_id") or ""), args[0] if args else "", True
        ))

    @bot.command(name="gcunwhitelist", aliases=["gcunwl"])
    def gcunwhitelist_cmd(ctx, args):
        _run(ctx, lambda: tools.whitelist(
            str(ctx.get("channel_id") or ""), args[0] if args else "", False
        ))

    @bot.command(name="gcremoveall")
    def gcremoveall_cmd(ctx, args):
        confirmed = bool(args and args[0].casefold() == "confirm")
        _run(ctx, lambda: tools.remove_all_members(
            str(ctx.get("channel_id") or ""), confirm=confirmed
        ))

    @bot.command(name="massgcleave", aliases=["gcleaveall"])
    def massgcleave_cmd(ctx, args):
        confirmed = bool(args and args[0].casefold() == "confirm")
        _run(ctx, lambda: tools.mass_leave(confirm=confirmed))

    return tools
