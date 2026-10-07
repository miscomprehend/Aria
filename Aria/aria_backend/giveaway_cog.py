"""
Aria — Giveaway sniper cog (modifyself).

Enters giveaways posted by bots/webhooks/apps (button first, then reactions)
and counts messages that congratulate you. Ported from giveaway.GiveawaySniper.
"""

import os
import re
import urllib.parse

from modifyself.commands.cog import Cog, listener
from modifyself.commands.core import command
from modifyself.http.route import Route

import ansi
import persistence
from ascii_helper import ASCIIMixin, send_temp
from giveaway import (
    GIVEAWAY_KEYWORDS,
    component_text,
    extract_entry_emojis,
    iter_component_nodes,
)

CATEGORY = "Giveaway"
CATEGORY_DESC = "Giveaway sniper"

COMMANDS_INFO = {
    "giveaway": ("giveaway <on/off/stats>", "Toggle the giveaway sniper or show stats"),
}

_ENTRY_TERMS = ("enter", "join", "participate", "entries", "entry", "claim", "giveaway")
_MESSAGE_FIELDS = (
    "id", "channel_id", "guild_id", "author", "webhook_id", "application_id",
    "content", "embeds", "components", "components_v2", "reactions", "mentions",
    "flags", "interaction_metadata",
)


def _g(o, k, d=None):
    if isinstance(o, dict):
        return o.get(k, d)
    return getattr(o, k, d)


def message_text(message) -> str:
    parts = [str(_g(message, "content", "") or "")]
    for embed in _g(message, "embeds", []) or []:
        parts.append(str(_g(embed, "title", "") or ""))
        parts.append(str(_g(embed, "description", "") or ""))
        for field in _g(embed, "fields", []) or []:
            parts.append(str(_g(field, "name", "") or ""))
            parts.append(str(_g(field, "value", "") or ""))
        parts.append(str(_g(_g(embed, "footer", {}) or {}, "text", "") or ""))
        parts.append(str(_g(_g(embed, "author", {}) or {}, "name", "") or ""))
    component_data = {
        "components": _g(message, "components", []) or [],
        "components_v2": _g(message, "components_v2", []) or [],
    }
    parts.append(component_text(component_data))
    return " ".join(parts)


def is_giveaway(message) -> bool:
    text = message_text(message).lower()
    return any(kw in text for kw in GIVEAWAY_KEYWORDS)


def iter_nodes(node):
    yield from iter_component_nodes(node)


def pick_button(message):
    roots = list(_g(message, "components", []) or []) + list(_g(message, "components_v2", []) or [])
    buttons = [n for n in iter_nodes(roots) if int(n.get("type") or 0) == 2 and n.get("custom_id")]
    for button in buttons:
        label = str(button.get("label") or "").lower()
        cid = str(button.get("custom_id") or "").lower()
        if any(term in label or term in cid for term in _ENTRY_TERMS):
            return button
    return buttons[0] if buttons else None


def encode_emoji(emoji) -> str:
    if not emoji:
        return ""
    if isinstance(emoji, str):
        if re.fullmatch(r"(?:a:)?[^:]+:\d{15,25}", emoji):
            return emoji.removeprefix("a:")
        return urllib.parse.quote(emoji)
    name, eid = _g(emoji, "name", "") or "", _g(emoji, "id")
    if eid:
        return f"{name}:{eid}"
    return urllib.parse.quote(name) if name else ""


def entry_emojis(message) -> list:
    found = []
    for reaction in _g(message, "reactions", []) or []:
        if _g(reaction, "me") or (_g(reaction, "count", 0) or 0) <= 0:
            continue
        enc = encode_emoji(_g(reaction, "emoji"))
        if enc:
            found.append(enc)
    found.extend(encode_emoji(emoji) for emoji in extract_entry_emojis(message_text(message)))
    return list(dict.fromkeys(found))


class Giveaway(Cog, ASCIIMixin):

    def __init__(self, bot):
        super().__init__(bot)
        cfg = persistence.get("giveaway_cfg", {}) or {}
        self.enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else False
        self.entered = set()
        self.entering = set()
        self._messages = {}
        self._won_messages = set()
        self.stats = {"entered": 0, "won": 0, "failed": 0}
        self.last_win = None

    def _save(self):
        persistence.set_key("giveaway_cfg", {"enabled": self.enabled})

    async def _my_id(self) -> str:
        user = getattr(self.bot, "user", None)
        return str(_g(user, "id", "") or "") if user else ""

    @staticmethod
    def _message_dict(message) -> dict:
        if isinstance(message, dict):
            return dict(message)
        return {key: getattr(message, key) for key in _MESSAGE_FIELDS if hasattr(message, key)}

    def _merge_message(self, message) -> dict:
        incoming = self._message_dict(message)
        mid = str(incoming.get("id") or "")
        if not mid:
            return incoming
        merged = dict(self._messages.get(mid, {}))
        merged.update(incoming)
        self._messages[mid] = merged
        if len(self._messages) > 500:
            self._messages.pop(next(iter(self._messages)))
        return merged

    @listener()
    async def on_message_create(self, message):
        if not self.enabled:
            return
        message = self._merge_message(message)
        author = _g(message, "author") or {}
        my_id = await self._my_id()
        if my_id and str(_g(author, "id", "") or "") == my_id:
            return
        self._check_win(message, my_id)
        if _g(author, "bot") or _g(message, "webhook_id") or _g(message, "application_id"):
            await self._try_enter(message)

    @listener()
    async def on_message_update(self, message):
        if not self.enabled:
            return
        message = self._merge_message(message)
        author = _g(message, "author") or {}
        my_id = await self._my_id()
        if my_id and str(_g(author, "id", "") or "") == my_id:
            return
        self._check_win(message, my_id)
        if _g(author, "bot") or _g(message, "webhook_id") or _g(message, "application_id"):
            await self._try_enter(message)

    def _check_win(self, message, my_id: str):
        if not my_id:
            return
        mid = str(_g(message, "id", "") or "")
        if mid and mid in self._won_messages:
            return
        content = message_text(message).lower()
        mentioned = f"<@{my_id}>" in content or f"<@!{my_id}>" in content or any(
            str(_g(m, "id", "")) == my_id for m in _g(message, "mentions", []) or []
        )
        if mentioned and any(w in content for w in ("congratulations", "congrats", "won", "winner", "🎉", "🎁")):
            if mid:
                self._won_messages.add(mid)
            self.stats["won"] += 1
            author = _g(message, "author") or {}
            self.last_win = _g(author, "username", "Unknown")
            print(f"[GIVEAWAY WIN] from {self.last_win}")

    async def _try_enter(self, message):
        if not is_giveaway(message):
            return
        mid = str(_g(message, "id", "") or "")
        if not mid or mid in self.entered or mid in self.entering:
            return
        if any(_g(r, "me") for r in _g(message, "reactions", []) or []):
            return
        self.entering.add(mid)
        try:
            button = pick_button(message)
            emojis = entry_emojis(message)
            ok = False
            if button:
                ok = await self._click(message, button)
            if not ok and emojis:
                ok = await self._react(message, emojis)
            if not ok and not button and not emojis:
                ok = await self._react(message, [urllib.parse.quote("🎉")])
            self.stats["entered" if ok else "failed"] += 1
            if ok:
                self.entered.add(mid)
            print(f"[GIVEAWAY] {'Entered' if ok else 'Failed'} msg={mid}")
        finally:
            self.entering.discard(mid)

    async def _click(self, message, button) -> bool:
        author = _g(message, "author") or {}
        app_id = str(_g(message, "application_id", "") or _g(author, "id", "") or "")
        session_id = str(getattr(self.bot, "session_id", "") or os.urandom(16).hex())
        payload = {
            "type": 3,
            "nonce": str(int.from_bytes(os.urandom(8), "big") % (10**19 - 10**18) + 10**18),
            "guild_id": _g(message, "guild_id"),
            "channel_id": _g(message, "channel_id"),
            "message_flags": _g(message, "flags", 0) or 0,
            "message_id": _g(message, "id"),
            "application_id": app_id,
            "session_id": session_id,
            "data": {"component_type": 2, "custom_id": button.get("custom_id")},
        }
        try:
            await self.bot._http.request(Route("POST", "/interactions"), json=payload)
            return True
        except Exception:
            return False

    async def _react(self, message, emojis) -> bool:
        cid, mid = _g(message, "channel_id"), _g(message, "id")
        ok = False
        for enc in emojis:
            try:
                await self.bot._http.request(
                    Route("PUT", f"/channels/{cid}/messages/{mid}/reactions/{enc}/@me")
                )
                ok = True
            except Exception:
                pass
        return ok

    def get_stats(self) -> dict:
        return {"enabled": self.enabled, **self.stats, "last_win": self.last_win}

    @command(name="giveaway", aliases=["gw", "gsnipe"])
    async def giveaway(self, ctx, *, value: str = ""):
        arg = (value or "").strip().lower()
        if arg in ("on", "enable"):
            self.enabled = True; self._save()
            await self.asuccess(ctx, "Giveaway sniper enabled.")
        elif arg in ("off", "disable"):
            self.enabled = False; self._save()
            await self.asuccess(ctx, "Giveaway sniper disabled.")
        elif arg in ("", "stats", "status"):
            s = self.get_stats()
            await send_temp(
                ctx,
                ansi.giveaway_status("ON" if s["enabled"] else "OFF", s["entered"], s["won"], s["failed"], s["last_win"]),
                20,
            )
        else:
            await send_temp(ctx, ansi.command_usage("giveaway", *COMMANDS_INFO["giveaway"], "."), 15)


def setup(bot):
    bot.add_cog(Giveaway(bot))
