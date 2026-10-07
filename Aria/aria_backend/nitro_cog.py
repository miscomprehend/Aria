"""
Aria — Nitro sniper cog (modifyself).

Watches MESSAGE_CREATE for Nitro gift links and redeems them through the
REST gift-code endpoint. Ported from the standalone nitro.NitroSniper.
"""

import re
import time

from modifyself.commands.cog import Cog, listener
from modifyself.commands.core import command
from modifyself.http.route import Route

import ansi
import persistence
from ascii_helper import ASCIIMixin, send_temp

CATEGORY = "Nitro"
CATEGORY_DESC = "Nitro gift sniper"

COMMANDS_INFO = {
    "nitro": ("nitro <on/off/clear/stats>", "Toggle the Nitro sniper, clear its cache or show stats"),
}

_URL_PATTERNS = (
    re.compile(r"discord\.gift/(\w{16,24})", re.I),
    re.compile(r"discord(?:app)?\.com/gifts/(\w{16,24})", re.I),
    re.compile(r"discord\.com/billing/promotions/(\w{16,24})", re.I),
)
_RAW_CODE = re.compile(r"\b([A-Za-z0-9]{16}|[A-Za-z0-9]{24})\b")
_CONTEXT_WORDS = ("nitro", "gift", "redeem")


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


def extract_codes(text: str) -> list:
    """Gift links always count; bare 16/24-char tokens only count with Nitro context."""
    codes = []
    for pattern in _URL_PATTERNS:
        codes.extend(pattern.findall(text))
    if any(word in text.lower() for word in _CONTEXT_WORDS):
        codes.extend(_RAW_CODE.findall(text))
    return list(dict.fromkeys(codes))


class Nitro(Cog, ASCIIMixin):

    def __init__(self, bot):
        super().__init__(bot)
        cfg = persistence.get("nitro_cfg", {}) or {}
        self.enabled = bool(cfg.get("enabled")) if isinstance(cfg, dict) else False
        self.used_codes = set()
        self.stats = {"attempted": 0, "claimed": 0, "failed": 0, "invalid": 0}
        self.last_claimed = None

    def _save(self):
        persistence.set_key("nitro_cfg", {"enabled": self.enabled})

    async def _my_id(self) -> str:
        user = getattr(self.bot, "user", None)
        return str(_g(user, "id", "") or "") if user else ""

    @listener()
    async def on_message_create(self, message):
        if not self.enabled:
            return
        author = _g(message, "author")
        if author and str(_g(author, "id", "") or "") == await self._my_id():
            return
        for code in extract_codes(message_text(message)):
            if code in self.used_codes:
                continue
            self.used_codes.add(code)
            await self._claim(code, message)

    async def _claim(self, code: str, message):
        self.stats["attempted"] += 1
        started = time.time()
        try:
            data = await self.bot._http.request(
                Route("POST", f"/entitlements/gift-codes/{code}/redeem"), json={}
            )
        except Exception as exc:
            text = str(exc).lower()
            if "already been redeemed" in text:
                self.stats["failed"] += 1
            elif "unknown gift code" in text or "invalid" in text:
                self.stats["invalid"] += 1
            else:
                self.stats["failed"] += 1
            print(f"[NITRO] {code}: {str(exc)[:80]} ({(time.time() - started) * 1000:.0f}ms)")
            return
        self.stats["claimed"] += 1
        author = _g(message, "author") or {}
        self.last_claimed = {
            "code": code,
            "sender": _g(author, "username", "Unknown"),
            "plan": _g(_g(data or {}, "subscription_plan", {}) or {}, "name", None),
        }
        print(f"[NITRO CLAIMED] {code} from {self.last_claimed['sender']}")

    def clear_codes(self) -> int:
        count = len(self.used_codes)
        self.used_codes.clear()
        self.stats = {"attempted": 0, "claimed": 0, "failed": 0, "invalid": 0}
        return count

    def get_stats(self) -> dict:
        return {
            "enabled": self.enabled,
            "claimed": self.stats["claimed"],
            "cached": len(self.used_codes),
            "last_claimed": (self.last_claimed or {}).get("sender"),
            **{k: v for k, v in self.stats.items() if k != "claimed"},
        }

    @command(name="nitro", aliases=["nitrosniper"])
    async def nitro(self, ctx, *, value: str = ""):
        arg = (value or "").strip().lower()
        if arg in ("on", "enable"):
            self.enabled = True; self._save()
            await self.asuccess(ctx, "Nitro sniper enabled.")
        elif arg in ("off", "disable"):
            self.enabled = False; self._save()
            await self.asuccess(ctx, "Nitro sniper disabled.")
        elif arg == "clear":
            await self.asuccess(ctx, f"Nitro cache cleared ({self.clear_codes()} codes).")
        elif arg in ("stats", "status"):
            s = self.get_stats()
            await send_temp(
                ctx,
                ansi.nitro_status("ON" if s["enabled"] else "OFF", s["claimed"], s["cached"], s["last_claimed"]),
                20,
            )
        else:
            await send_temp(ctx, ansi.command_usage("nitro", *COMMANDS_INFO["nitro"], "."), 15)


def setup(bot):
    bot.add_cog(Nitro(bot))
