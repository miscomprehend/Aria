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

CATEGORY = "Giveaway"
CATEGORY_DESC = "Giveaway sniper"

COMMANDS_INFO = {
    "giveaway": ("giveaway <on/off/stats>", "Toggle the giveaway sniper or show stats"),
}

GIVEAWAY_KEYWORDS = (
    "giveaway", "prize", "hosted by", "ends in", "react to win", "🎉",
    "winner", "raffle", "claim your prize",
)
_ENTRY_TERMS = ("enter", "join", "participate", "entries", "entry", "claim", "giveaway")
_UNICODE_ENTRY = ("🎉", "🎁", "🪅", "🥳", "✅", "🎊", "🎈")
_CUSTOM_EMOJI = re.compile(r"<(a?):([^:>]+):([0-9]{15,25})>")


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
    return " ".join(parts)


def is_giveaway(message) -> bool:
    text = message_text(message).lower()
    return any(kw in text for kw in GIVEAWAY_KEYWORDS)


def iter_nodes(node):
    if isinstance(node, list):
        for item in node:
            yield from iter_nodes(item)
    elif isinstance(node, dict):
        yield node
        for key in ("components", "items", "accessory", "children"):
            if node.get(key):
                yield from iter_nodes(node[key])


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
        return urllib.parse.quote(emoji)
    name, eid = emoji.get("name") or "", emoji.get("id")
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
    text = message_text(message)
    lowered = text.lower()
    custom = _CUSTOM_EMOJI.search(text)
    if custom:
        found.append(f"{custom.group(2)}:{custom.group(3)}")
    elif any(w in lowered for w in ("react", "entry", "enter")):
        for emoji in _UNICODE_ENTRY:
            if emoji in text:
                found.append(urllib.parse.quote(emoji))
                break
    return list(dict.fromkeys(found))


class Giveaway(Cog, ASCIIMixin):

    def __init__(self, bot):
        super().__init__(bot)
        cfg = persistence.get("giveaway_cfg", {}) or {}
        self.enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else False
        self.entered = set()
        self.stats = {"entered": 0, "won": 0, "failed": 0}
        self.last_win = None

    def _save(self):
        persistence.set_key("giveaway_cfg", {"enabled": self.enabled})

    async def _my_id(self) -> str:
        user = getattr(self.bot, "user", None)
        return str(_g(user, "id", "") or "") if user else ""

    @listener()
    async def on_message_create(self, message):
        if not self.enabled:
            return
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
        content = str(_g(message, "content", "") or "").lower()
        mentioned = f"<@{my_id}>" in content or f"<@!{my_id}>" in content or any(
            str(_g(m, "id", "")) == my_id for m in _g(message, "mentions", []) or []
        )
        if mentioned and any(w in content for w in ("congratulations", "won", "winner", "🎉")):
            self.stats["won"] += 1
            author = _g(message, "author") or {}
            self.last_win = _g(author, "username", "Unknown")
            print(f"[GIVEAWAY WIN] from {self.last_win}")

    async def _try_enter(self, message):
        if not is_giveaway(message):
            return
        mid = str(_g(message, "id", "") or "")
        if not mid or mid in self.entered:
            return
        if any(_g(r, "me") for r in _g(message, "reactions", []) or []):
            return
        self.entered.add(mid)

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
        print(f"[GIVEAWAY] {'Entered' if ok else 'Failed'} msg={mid}")

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
