"""
Aria — OwO farm cog (modifyself).

Sends configurable OwO commands (default wh, wb) to a farm channel on a
randomized loop and stops itself on any captcha/ban message from OwO.
Ported from cupnodeles/OwO_auto (config, once, start/stop, delays).
"""

import asyncio
import random

from modifyself.commands.cog import Cog, listener
from modifyself.commands.core import command
from modifyself.http.route import Route

import persistence
from ascii_helper import ASCIIMixin, send_temp

CATEGORY = "OwO"
CATEGORY_DESC = "OwO farm automation"

COMMANDS_INFO = {
    "owofarm": (
        "owofarm <start/stop/once/status/check/channel/cmds/add/remove/up/down/delay>",
        "Run and configure the OwO farm loop",
    ),
}

OWO_BOT_ID = "408785106942164992"
STOP_WORDS = ("captcha", "are you a real human", "verify", "banned", "warning")
DEFAULTS = {"channel_id": "", "commands": ["wh", "wb"], "cmd_gap": 0.6, "delay_min": 11.0, "delay_max": 19.0}

USAGE = (
    "owofarm start | stop | once | status | check\n"
    "owofarm channel [id] | cmds | add <cmd> | remove <n> | up <n> | down <n>\n"
    "owofarm delay <min> <max> [gap]"
)


def _g(o, k, d=None):
    if isinstance(o, dict):
        return o.get(k, d)
    return getattr(o, k, d)


class OwoFarm(Cog, ASCIIMixin):

    def __init__(self, bot):
        super().__init__(bot)
        saved = persistence.get("owo_cfg", {}) or {}
        self.cfg = {**DEFAULTS, **(saved if isinstance(saved, dict) else {})}
        self.cfg["commands"] = list(self.cfg["commands"])
        self.task = None
        self.cycles = 0

    def _save(self):
        persistence.set_key("owo_cfg", self.cfg)

    @property
    def running(self) -> bool:
        return bool(self.task and not self.task.done())

    @staticmethod
    def _cid(ctx) -> str:
        v = getattr(ctx, "channel_id", None)
        if v:
            return str(v)
        m = getattr(ctx, "message", None)
        v = getattr(m, "channel_id", None)
        if v:
            return str(v)
        ch = getattr(ctx, "channel", None) or getattr(m, "channel", None)
        return str(getattr(ch, "id", "") or "")

    async def _post(self, content: str):
        await self.bot._http.request(
            Route("POST", f"/channels/{self.cfg['channel_id']}/messages"),
            json={"content": content},
        )

    async def _send_cycle(self):
        cmds = self.cfg["commands"]
        for i, cmd in enumerate(cmds):
            await self._post(cmd)
            if i < len(cmds) - 1:
                await asyncio.sleep(self.cfg["cmd_gap"])

    async def _loop(self):
        try:
            while True:
                await self._send_cycle()
                self.cycles += 1
                await asyncio.sleep(random.uniform(self.cfg["delay_min"], self.cfg["delay_max"]))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[OWO] loop stopped: {str(exc)[:100]}")

    @listener()
    async def on_message_create(self, message):
        if not self.running:
            return
        if str(_g(_g(message, "author") or {}, "id", "") or "") != OWO_BOT_ID:
            return
        cid = str(_g(message, "channel_id", "") or "")
        in_dm = not _g(message, "guild_id")
        if not (in_dm or cid == str(self.cfg["channel_id"])):
            return
        text = str(_g(message, "content", "") or "").lower()
        if any(w in text for w in STOP_WORDS):
            self.task.cancel()
            print("[OWO] captcha/warning detected, farm stopped")

    @command(name="owofarm", aliases=["owof"])
    async def owofarm(self, ctx, *, value: str = ""):
        parts = (value or "").strip().split()
        sub = parts[0].lower() if parts else "status"
        args = parts[1:]
        cmds = self.cfg["commands"]

        if sub == "start":
            if self.running:
                await self.awarn(ctx, "Already running.")
            elif not self.cfg["channel_id"]:
                await self.aerror(ctx, "Set a channel first: owofarm channel")
            else:
                self.cycles = 0
                self.task = asyncio.ensure_future(self._loop())
                await self.asuccess(ctx, "Farm started. Auto-stops on captcha/warning.")
        elif sub == "stop":
            if self.running:
                self.task.cancel()
                await self.asuccess(ctx, f"Farm stopped after {self.cycles} cycles.")
            else:
                await self.awarn(ctx, "Not running.")
        elif sub == "once":
            if not self.cfg["channel_id"]:
                await self.aerror(ctx, "Set a channel first: owofarm channel")
                return
            try:
                await self._send_cycle()
            except Exception as exc:
                await self.aerror(ctx, f"Send failed: {str(exc)[:80]}")
        elif sub == "check":
            ok = bool(self.cfg["channel_id"])
            await self.aprint(ctx, "OwO check", [
                f"channel: {self.cfg['channel_id'] or 'not set'}",
                f"commands: {', '.join(cmds) or 'none'}",
                "ready" if ok else "set a channel first",
            ])
        elif sub == "channel":
            cid = args[0] if args and args[0].isdigit() else self._cid(ctx)
            if not cid:
                await self.aerror(ctx, "Could not determine channel id.")
                return
            self.cfg["channel_id"] = cid; self._save()
            await self.asuccess(ctx, f"Farm channel set to {cid}.")
        elif sub in ("cmds", "list"):
            await self.aprint(ctx, "OwO commands", [f"{i + 1}. {c}" for i, c in enumerate(cmds)] or ["none"])
        elif sub == "add" and args:
            cmds.append(" ".join(args)); self._save()
            await self.asuccess(ctx, f"Added {' '.join(args)}.")
        elif sub in ("remove", "up", "down") and args and args[0].isdigit():
            n = int(args[0])
            if sub == "remove" and 1 <= n <= len(cmds):
                removed = cmds.pop(n - 1); self._save()
                await self.asuccess(ctx, f"Removed {removed}.")
            elif sub == "up" and 2 <= n <= len(cmds):
                cmds[n - 2], cmds[n - 1] = cmds[n - 1], cmds[n - 2]; self._save()
                await self.asuccess(ctx, "Moved up.")
            elif sub == "down" and 1 <= n < len(cmds):
                cmds[n], cmds[n - 1] = cmds[n - 1], cmds[n]; self._save()
                await self.asuccess(ctx, "Moved down.")
            else:
                await self.aerror(ctx, "Invalid position.")
        elif sub == "delay" and len(args) >= 2:
            try:
                lo, hi = float(args[0]), float(args[1])
                gap = float(args[2]) if len(args) > 2 else self.cfg["cmd_gap"]
            except ValueError:
                await self.aerror(ctx, "Delays must be numbers.")
                return
            if lo <= 0 or hi < lo or gap < 0:
                await self.aerror(ctx, "Invalid range.")
                return
            self.cfg.update(delay_min=lo, delay_max=hi, cmd_gap=gap); self._save()
            await self.asuccess(ctx, f"Delay {lo}-{hi}s, gap {gap}s.")
        elif sub in ("status", ""):
            await self.aprint(ctx, "OwO farm", [
                f"running: {self.running} ({self.cycles} cycles)",
                f"channel: {self.cfg['channel_id'] or 'not set'}",
                f"commands: {', '.join(cmds) or 'none'}",
                f"delay: {self.cfg['delay_min']}-{self.cfg['delay_max']}s, gap {self.cfg['cmd_gap']}s",
            ], delay=20)
        else:
            await send_temp(ctx, USAGE, 15)

    @command(name="owo")
    async def owo(self, ctx):
        await self.asuccess(ctx, "OwO! You look amazing today!")

    @command(name="uwu")
    async def uwu(self, ctx):
        await self.asuccess(ctx, "UwU! You're so adorable!")


def setup(bot):
    bot.add_cog(OwoFarm(bot))
