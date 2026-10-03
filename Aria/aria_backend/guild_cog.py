"""
Aria — Guild cog (modifyself).

Server-list + your-own-account server tools: list guilds, leave all non-owned
servers, set/clear your clan (guild) tag, and rotate the tag across servers.

(The destructive server-wipe "clone" command is intentionally not included.)

Logic lives in reusable methods so the selfbot and /slash commands share it.
"""


import asyncio
import logging
import math
import random

from modifyself.commands.cog import Cog
from modifyself.commands.core import command
from modifyself.http.route import Route

import ansi
from ascii_helper import send_temp

CATEGORY = "Guild"
CATEGORY_DESC = "Server management"
_LOGGER = logging.getLogger(__name__)

COMMANDS_INFO = {
    "guilds":         ("guilds [page]", "List all servers you're in with member counts"),
    "massleave":      ("massleave [id,id,...]", "Leave all non-owned servers (optional excludes)"),
    "setclan":        ("setclan <guild_id>", "Set your clan tag to a server you're in"),
    "clearclan":      ("clearclan", "Clear your current clan tag"),
    "rotatetags":     ("rotatetags <i1> <i2> ... [Nm]", "Rotate clan tags across servers by index"),
    "stoprotatetags": ("stoprotatetags", "Stop guild tag rotation"),
}


class Guild(Cog):

    def __init__(self, bot):
        super().__init__(bot)
        self._rot_task = None

    def stop(self):
        if self._rot_task is not None:
            try:
                self._rot_task.cancel()
            except Exception:
                pass
        self._rot_task = None

    # ── helpers ──────────────────────────────────────────────────────────
    async def _guilds(self, counts=False) -> list:
        path = "/users/@me/guilds" + ("?with_counts=true" if counts else "")
        try:
            guilds = await self.bot._http.request(Route("GET", path))
        except Exception as exc:
            raise RuntimeError(f"Couldn't fetch your servers: {exc}") from exc
        if not isinstance(guilds, list):
            raise RuntimeError("Discord returned an invalid server list.")
        return guilds

    async def _set_clan(self, gid, enabled: bool):
        result = await self.bot._http.request(
            Route("PUT", "/users/@me/clan"),
            json={"identity_guild_id": gid, "identity_enabled": enabled})
        status = getattr(result, "status", getattr(result, "status_code", None))
        if status is not None and status not in (200, 204):
            raise RuntimeError(f"Discord returned HTTP {status}.")
        return result

    # ── logic (return ANSI strings) ──────────────────────────────────────
    async def list_block(self, page: int = 1) -> str:
        try:
            gs = await self._guilds(counts=True)
        except RuntimeError as exc:
            return ansi.error(str(exc))
        if not gs:
            return ansi.warning("This account is not in any servers.")
        per = 8
        total = len(gs)
        pages = max(1, (total + per - 1) // per)
        page = max(1, min(page, pages))
        chunk = gs[(page - 1) * per: page * per]
        pairs = []
        for g in chunk:
            name = (g.get("name") or "?")[:24]
            gid = g.get("id", "?")
            count = g.get("approximate_member_count", "?")
            owner = " · owner" if g.get("owner") else ""
            pairs.append((name, f"{count} · {gid}{owner}"))
        return (ansi.header(f"guilds [{total}] · {page}/{pages}") + "\n" + ansi.command_list(pairs))

    async def mass_leave(self, exclude: set) -> str:
        invalid_excludes = sorted(value for value in exclude if not str(value).isdigit())
        if invalid_excludes:
            return ansi.error("Invalid server ID(s) in exclude list.")
        try:
            gs = await self._guilds()
        except RuntimeError as exc:
            return ansi.error(str(exc))
        targets = [g for g in gs if not g.get("owner") and str(g.get("id")) not in exclude]
        if not targets:
            return ansi.error("No leavable servers (owned & excluded are skipped).")
        left = failed = 0
        for g in targets:
            try:
                result = await self.bot._http.request(
                    Route("DELETE", f"/users/@me/guilds/{g['id']}"), json={"lurking": False})
                status = getattr(result, "status", getattr(result, "status_code", None))
                if status is not None and status not in (200, 204):
                    raise RuntimeError(f"Discord returned HTTP {status}.")
                left += 1
            except Exception:
                failed += 1
            await asyncio.sleep(random.uniform(1.0, 2.0))
        return (ansi.header("mass leave") + "\n"
                + ansi.command_list([("Left", f"{left}/{len(targets)}"), ("Failed", str(failed))]))

    async def set_clan(self, gid: str) -> str:
        gid = (gid or "").strip()
        if not gid.isdigit():
            return ansi.error("Invalid guild id.")
        try:
            data = await self._set_clan(gid, True)
            clan = (data or {}).get("clan") or (data or {}).get("primary_guild") or {}
            tag = clan.get("tag", "?")
            return ansi.success(f"Clan tag set to [{tag}] (guild {gid}).")
        except Exception as e:
            return ansi.error(f"Failed to set clan: {e}")

    async def clear_clan(self) -> str:
        try:
            await self._set_clan(None, False)
            return ansi.success("Clan tag cleared.")
        except Exception as e:
            return ansi.error(f"Failed: {e}")

    async def _rotate_loop(self, indexes: list, delay_mins: float):
        counter = 0
        while True:
            try:
                gs = await self._guilds()
                if gs:
                    idx = indexes[counter % len(indexes)]
                    if 1 <= idx <= len(gs):
                        await self._set_clan(gs[idx - 1]["id"], True)
                    else:
                        _LOGGER.warning("Clan-tag rotation index %s exceeds current server count %s", idx, len(gs))
                counter += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Clan-tag rotation failed; it will retry after the configured interval")
            await asyncio.sleep(max(60, delay_mins * 60))

    def start_rotation(self, value: str) -> str:
        parts = (value or "").split()
        delay = 10.0
        if parts and parts[-1].lower().endswith("m"):
            try:
                delay = float(parts[-1][:-1])
            except ValueError:
                return ansi.error("Usage: rotatetags <1 2 3...> [1-1440m]")
            parts = parts[:-1]
        if (
            not math.isfinite(delay)
            or not 1 <= delay <= 1440
            or not parts
            or any(not part.isdigit() or int(part) < 1 for part in parts)
        ):
            return ansi.error("Usage: rotatetags <1 2 3...> [1-1440m]")
        indexes = list(dict.fromkeys(int(part) for part in parts))
        self.stop()
        try:
            self._rot_task = asyncio.get_running_loop().create_task(self._rotate_loop(indexes, delay))
        except RuntimeError:
            return ansi.error("Clan-tag rotation requires an active client event loop.")
        return ansi.success(f"Rotating {len(indexes)} tag(s) every {delay} min.")

    def stop_rotation(self) -> str:
        if self._rot_task is not None and not self._rot_task.done():
            self.stop()
            return ansi.success("Stopped guild tag rotation.")
        return ansi.error("No tag rotation active.")

    # ── selfbot commands ─────────────────────────────────────────────────
    @command(name="guilds", aliases=["servers", "guildlist"])
    async def guilds(self, ctx, *, value: str = ""):
        try:
            page = max(1, int(value.strip())) if value.strip() else 1
        except ValueError:
            page = 1
        await send_temp(ctx, await self.list_block(page), 25)

    @command(name="massleave", aliases=["leaveall"])
    async def massleave(self, ctx, *, value: str = ""):
        exclude = {p.strip() for p in value.split(",") if p.strip()}
        await send_temp(ctx, await self.mass_leave(exclude), 15)

    @command(name="setclan", aliases=["clanset", "settag"])
    async def setclan(self, ctx, *, value: str = ""):
        if not value.strip():
            await send_temp(ctx, ansi.command_usage("setclan", *COMMANDS_INFO["setclan"], "."), 10)
            return
        await send_temp(ctx, await self.set_clan(value), 10)

    @command(name="clearclan", aliases=["removeclan", "cleartag"])
    async def clearclan(self, ctx, *, value: str = ""):
        await send_temp(ctx, await self.clear_clan(), 10)

    @command(name="rotatetags")
    async def rotatetags(self, ctx, *, value: str = ""):
        if not value.strip():
            await send_temp(ctx, ansi.command_usage("rotatetags", *COMMANDS_INFO["rotatetags"], "."), 10)
            return
        await send_temp(ctx, self.start_rotation(value), 12)

    @command(name="stoprotatetags")
    async def stoprotatetags(self, ctx, *, value: str = ""):
        await send_temp(ctx, self.stop_rotation(), 10)

def setup(bot):
    bot.add_cog(Guild(bot))
