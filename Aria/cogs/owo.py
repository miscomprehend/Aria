import asyncio
import base64
import json
import os
import random

from discord.ext import commands  # type: ignore
from quest_system.captcha import get_captcha_solver

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "owo_config.json")
OWO_BOT_ID = 408785106942164992
STOP_WORDS = ("captcha", "are you a real human", "verify", "banned", "warning")

DEFAULTS = {
    "channel_id": None,
    "commands": ["wh", "wb"],
    "cmd_gap": 0.6,
    "delay_min": 11.0,
    "delay_max": 19.0,
}


def _load():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


class Owo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cfg = _load()
        self.task = None
        self.cycles = 0
        self.paused = False
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.captcha_solver = get_captcha_solver()

    def cog_unload(self):
        if self.task and not self.task.done():
            self.task.cancel()

    def _save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cfg, f, indent=2)

    def _channel(self):
        cid = self.cfg.get("channel_id")
        return self.bot.get_channel(int(cid)) if cid else None

    async def _send_cycle(self, channel):
        cmds = self.cfg["commands"]
        for i, cmd in enumerate(cmds):
            await self.pause_event.wait()
            await channel.send(cmd)
            if i < len(cmds) - 1:
                await self._sleep_with_pause(self.cfg["cmd_gap"])

    async def _sleep_with_pause(self, delay: float):
        deadline = asyncio.get_running_loop().time() + max(0.0, delay)
        while True:
            await self.pause_event.wait()
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(0.5, remaining))

    def _pause(self):
        self.paused = True
        self.pause_event.clear()

    def _resume(self):
        self.paused = False
        self.pause_event.set()

    async def _solve_image_captcha(self, message):
        attachments = getattr(message, "attachments", None) or []
        image = next(
            (
                a
                for a in attachments
                if (getattr(a, "content_type", "") or "").startswith("image/")
                or str(getattr(a, "filename", "") or "").lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp", ".gif")
                )
            ),
            None,
        )
        if image is None:
            return None

        try:
            image_bytes = await image.read()
        except Exception as exc:
            print(f"[OWO] failed to read captcha image: {exc}")
            return None
        if not image_bytes:
            return None

        try:
            image_base64 = base64.b64encode(image_bytes).decode("ascii")
            return await self.captcha_solver.solve_image_captcha(image_base64)
        except Exception as exc:
            print(f"[OWO] failed to solve image captcha: {exc}")
            return None

    async def _loop(self):
        while True:
            await self.pause_event.wait()
            channel = self._channel()
            if channel is None:
                return
            await self._send_cycle(channel)
            self.cycles += 1
            await self._sleep_with_pause(random.uniform(self.cfg["delay_min"], self.cfg["delay_max"]))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not (self.task and not self.task.done()):
            return
        if message.author.id != OWO_BOT_ID:
            return
        in_dm = message.guild is None
        in_farm = message.channel.id == self.cfg.get("channel_id")
        if not (in_dm or in_farm):
            return
        text = (message.content or "").lower()
        if any(w in text for w in STOP_WORDS):
            self._pause()
            solution = await self._solve_image_captcha(message)
            if solution:
                try:
                    await message.channel.send(solution)
                    self._resume()
                    return
                except Exception as exc:
                    print(f"[OWO] failed to send captcha solution: {exc}")
            try:
                await message.channel.send("Captcha/warning detected. Farming paused; use owopause/oworesume.")
            except Exception as exc:
                print(f"[OWO] failed to send pause notice: {exc}")

    @commands.command(name="owo", help="Simulates an owo interaction")
    async def owo(self, ctx):
        await ctx.send("OwO! You look amazing today!")

    @commands.command(name="uwu", help="Simulates an uwu interaction")
    async def uwu(self, ctx):
        await ctx.send("UwU! You're so adorable!")

    @commands.command(name="owochannel", help="Set the farm channel (defaults to current)")
    async def owochannel(self, ctx, channel_id: int | None = None):
        self.cfg["channel_id"] = channel_id or ctx.channel.id
        self._save()
        await ctx.send(f"Farm channel set to {self.cfg['channel_id']}.")

    @commands.command(name="owocmds", help="List the farm commands")
    async def owocmds(self, ctx):
        listing = ", ".join(f"{i + 1}:{c}" for i, c in enumerate(self.cfg["commands"])) or "none"
        await ctx.send(f"Commands: {listing}")

    @commands.command(name="owoadd", help="Add a farm command")
    async def owoadd(self, ctx, *, command: str):
        self.cfg["commands"].append(command)
        self._save()
        await ctx.send(f"Added `{command}`.")

    @commands.command(name="oworemove", help="Remove a farm command by position")
    async def oworemove(self, ctx, index: int):
        if not 1 <= index <= len(self.cfg["commands"]):
            await ctx.send("Invalid position.")
            return
        removed = self.cfg["commands"].pop(index - 1)
        self._save()
        await ctx.send(f"Removed `{removed}`.")

    @commands.command(name="owoup", help="Move a farm command up")
    async def owoup(self, ctx, index: int):
        cmds = self.cfg["commands"]
        if not 2 <= index <= len(cmds):
            await ctx.send("Invalid position.")
            return
        cmds[index - 2], cmds[index - 1] = cmds[index - 1], cmds[index - 2]
        self._save()
        await ctx.send("Moved up.")

    @commands.command(name="owodown", help="Move a farm command down")
    async def owodown(self, ctx, index: int):
        cmds = self.cfg["commands"]
        if not 1 <= index < len(cmds):
            await ctx.send("Invalid position.")
            return
        cmds[index], cmds[index - 1] = cmds[index - 1], cmds[index]
        self._save()
        await ctx.send("Moved down.")

    @commands.command(name="owodelay", help="Set loop delay range and command gap: owodelay <min> <max> [gap]")
    async def owodelay(self, ctx, delay_min: float, delay_max: float, gap: float | None = None):
        if delay_min <= 0 or delay_max < delay_min:
            await ctx.send("Invalid range.")
            return
        self.cfg["delay_min"], self.cfg["delay_max"] = delay_min, delay_max
        if gap is not None:
            self.cfg["cmd_gap"] = max(0.0, gap)
        self._save()
        await ctx.send(f"Delay {delay_min}-{delay_max}s, gap {self.cfg['cmd_gap']}s.")

    @commands.command(name="owocheck", help="Verify the farm channel is reachable")
    async def owocheck(self, ctx):
        channel = self._channel()
        if channel is None:
            await ctx.send("Farm channel not set or not visible. Use owochannel.")
            return
        await ctx.send(f"OK: {channel} ({channel.id}), commands {self.cfg['commands']}.")

    @commands.command(name="owoonce", help="Send one farm cycle")
    async def owoonce(self, ctx):
        channel = self._channel()
        if channel is None:
            await ctx.send("Farm channel not set. Use owochannel.")
            return
        await self._send_cycle(channel)

    @commands.command(name="owostart", help="Start the farm loop")
    async def owostart(self, ctx):
        if self.task and not self.task.done():
            await ctx.send("Already running.")
            return
        if self._channel() is None:
            await ctx.send("Farm channel not set. Use owochannel.")
            return
        self.cycles = 0
        self._resume()
        self.task = asyncio.create_task(self._loop())
        await ctx.send("Farm started. Auto-pauses on an OwO captcha or warning.")

    @commands.command(name="owostop", help="Stop the farm loop")
    async def owostop(self, ctx):
        if self.task and not self.task.done():
            self.task.cancel()
            self._resume()
            await ctx.send(f"Stopped after {self.cycles} cycles.")
        else:
            await ctx.send("Not running.")

    @commands.command(name="owopause", help="Pause the farm loop without stopping")
    async def owopause(self, ctx):
        if not (self.task and not self.task.done()):
            await ctx.send("Not running.")
            return
        if self.paused:
            await ctx.send("Already paused.")
            return
        self._pause()
        await ctx.send("Farm paused.")

    @commands.command(name="oworesume", help="Resume a paused farm loop")
    async def oworesume(self, ctx):
        if not (self.task and not self.task.done()):
            await ctx.send("Not running.")
            return
        if not self.paused:
            await ctx.send("Farm is already active.")
            return
        self._resume()
        await ctx.send("Farm resumed.")

    @commands.command(name="owostatus", help="Show farm status and settings")
    async def owostatus(self, ctx):
        running = bool(self.task and not self.task.done())
        await ctx.send(
            f"Running: {running} | paused: {self.paused} | cycles: {self.cycles} | channel: {self.cfg['channel_id']} | "
            f"commands: {self.cfg['commands']} | delay: {self.cfg['delay_min']}-{self.cfg['delay_max']}s | "
            f"gap: {self.cfg['cmd_gap']}s"
        )


async def setup(bot):
    await bot.add_cog(Owo(bot))