"""Native friend tools for Aria's single-account API client."""

from __future__ import annotations

import threading
from typing import Any, Callable


class FriendsTools:
    def __init__(self, api: Any):
        self.api = api
        self.autoreply: dict[str, str] = {}
        self._lock = threading.RLock()

    def _relationships(self) -> list[dict]:
        response = self.api.request("GET", "/users/@me/relationships")
        if response is None or getattr(response, "status_code", 0) != 200:
            status = getattr(response, "status_code", "no response")
            raise RuntimeError(f"Could not load relationships (HTTP {status})")
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError("Discord returned an invalid relationships response")
        return data

    @staticmethod
    def _user_id(value: str) -> str:
        user_id = str(value or "").strip().strip("<@!>")
        if not user_id.isdigit():
            raise ValueError("Provide a numeric user ID or mention.")
        return user_id

    def relationship_list(self, relationship_type: int) -> list[str]:
        relationships = self._relationships()
        lines = []
        for relationship in relationships:
            if relationship.get("type") != relationship_type:
                continue
            user = relationship.get("user") or {}
            user_id = str(user.get("id") or "")
            name = str(user.get("global_name") or user.get("username") or user_id or "Unknown")
            if user_id:
                lines.append(f"{name} :: {user_id}")
        return lines

    def add_friend(self, value: str) -> str:
        try:
            user_id = self._user_id(value)
            response = self.api.request(
                "PUT", f"/users/@me/relationships/{user_id}", data={}
            )
            if response is not None and response.status_code in (200, 201, 204):
                return f"Friend request sent to {user_id}."
            status = getattr(response, "status_code", "no response")
            return f"Friend request failed (HTTP {status})."
        except (ValueError, RuntimeError) as exc:
            return str(exc)
        except Exception as exc:
            return f"Friend request failed: {exc}"

    def remove_friend(self, value: str) -> str:
        try:
            user_id = self._user_id(value)
            response = self.api.request("DELETE", f"/users/@me/relationships/{user_id}")
            if response is not None and response.status_code in (200, 204):
                return f"Removed friend {user_id}."
            status = getattr(response, "status_code", "no response")
            return f"Friend removal failed (HTTP {status})."
        except (ValueError, RuntimeError) as exc:
            return str(exc)
        except Exception as exc:
            return f"Friend removal failed: {exc}"

    def configure_autoreply(self, value: str) -> str:
        parts = str(value or "").split(maxsplit=1)
        if len(parts) != 2:
            return "Usage: autoreply <user_id> <message>"
        try:
            user_id = self._user_id(parts[0])
        except ValueError as exc:
            return str(exc)
        message = parts[1].strip()
        if not message:
            return "Provide a reply message."
        if len(message) > 2000:
            return "Reply messages must be 2000 characters or fewer."
        with self._lock:
            self.autoreply[user_id] = message
        return f"Auto-reply enabled for {user_id}."

    def stop_autoreply(self, value: str = "") -> str:
        target = str(value or "").strip()
        with self._lock:
            if not target:
                count = len(self.autoreply)
                self.autoreply.clear()
                return f"Auto-reply disabled for {count} user(s)."
            try:
                user_id = self._user_id(target)
            except ValueError as exc:
                return str(exc)
            if self.autoreply.pop(user_id, None) is None:
                return f"No auto-reply is configured for {user_id}."
        return f"Auto-reply disabled for {user_id}."

    def auto_reply_state(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {"user_id": user_id, "message": message}
                for user_id, message in sorted(self.autoreply.items())
            ]

    def on_message_create(self, message: dict, owner_id: str) -> None:
        author = message.get("author") or {}
        author_id = str(author.get("id") or "")
        if not author_id or author_id == str(owner_id or "") or author.get("bot"):
            return
        channel_id = str(message.get("channel_id") or "")
        if not channel_id:
            return
        with self._lock:
            reply = self.autoreply.get(author_id)
        if reply:
            self.api.send_message(channel_id, reply)


def setup_friends_tools(bot: Any, is_control_user: Callable[[str], bool]) -> FriendsTools:
    tools = FriendsTools(bot.api)
    bot.friends_tools = tools

    def _send(ctx: dict, text: str) -> None:
        ctx["api"].send_message(ctx["channel_id"], f"> **Friends** :: {text}")

    def _authorized(ctx: dict) -> bool:
        if is_control_user(str(ctx.get("author_id") or "")):
            return True
        _send(ctx, "Owner/Admin only.")
        return False

    @bot.command(name="friend")
    def friend_cmd(ctx, args):
        if _authorized(ctx):
            _send(ctx, tools.add_friend(args[0] if args else ""))

    @bot.command(name="unfriend")
    def unfriend_cmd(ctx, args):
        if _authorized(ctx):
            _send(ctx, tools.remove_friend(args[0] if args else ""))

    for command_name, relationship_type, label in (
        ("pending", 3, "Incoming friend requests"),
        ("outgoing", 4, "Outgoing friend requests"),
        ("blocked", 2, "Blocked users"),
    ):
        def _list_cmd(ctx, args, relationship_type=relationship_type, label=label):
            if not _authorized(ctx):
                return
            try:
                lines = tools.relationship_list(relationship_type)
            except Exception as exc:
                _send(ctx, f"{label} could not be loaded: {exc}")
                return
            _send(ctx, f"{label} ({len(lines)}):\n" + ("\n".join(lines[:20]) or "None"))

        bot.command(name=command_name)(_list_cmd)

    @bot.command(name="autoreply")
    def autoreply_cmd(ctx, args):
        if _authorized(ctx):
            _send(ctx, tools.configure_autoreply(" ".join(args)))

    @bot.command(name="autoreplystop")
    def autoreply_stop_cmd(ctx, args):
        if _authorized(ctx):
            _send(ctx, tools.stop_autoreply(args[0] if args else ""))

    @bot.command(name="friendlink", aliases=["finvite"])
    def friendlink_cmd(ctx, args):
        if not _authorized(ctx):
            return
        try:
            days = int(args[0]) if args else 7
            max_uses = int(args[1]) if len(args) > 1 else 10
        except ValueError:
            _send(ctx, f"Usage: {bot.prefix}friendlink [days] [max_uses]")
            return
        if not 1 <= days <= 30 or not 1 <= max_uses <= 100:
            _send(ctx, "Invite expiry must be 1-30 days and uses must be 1-100.")
            return
        try:
            response = bot.api.request(
                "POST",
                "/users/@me/invites",
                data={
                    "max_age": days * 86400,
                    "max_uses": max_uses,
                    "temporary": False,
                    "target_type": 2,
                },
            )
            payload = response.json() if response is not None and response.status_code in (200, 201) else {}
            invite_code = str(payload.get("code") or "")
            _send(ctx, f"Invite: https://discord.gg/{invite_code}" if invite_code else
                  f"Invite creation failed (HTTP {getattr(response, 'status_code', 'no response')}).")
        except Exception as exc:
            _send(ctx, f"Invite creation failed: {exc}")

    return tools
