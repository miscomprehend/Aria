import asyncio, os, sys, types, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _stub_modifyself():
    class Cog:
        def __init__(self, bot): self.bot = bot
    def listener(*a, **k): return lambda f: f
    def command(*a, **k): return lambda f: f
    class Route:
        def __init__(self, method, path): self.method, self.path = method, path
    for name, attrs in {
        "modifyself": {}, "modifyself.commands": {},
        "modifyself.commands.cog": {"Cog": Cog, "listener": listener},
        "modifyself.commands.core": {"command": command},
        "modifyself.http": {}, "modifyself.http.route": {"Route": Route},
    }.items():
        mod = types.ModuleType(name); mod.__dict__.update(attrs)
        sys.modules.setdefault(name, mod)


_stub_modifyself()
import persistence  # noqa: E402
persistence.get = lambda k, d=None: d
persistence.set_key = lambda k, v: None
import owo_cog  # noqa: E402


class FakeHttp:
    def __init__(self): self.calls = []
    async def request(self, route, **kw):
        self.calls.append((route.method, route.path, kw))


class FakeBot:
    def __init__(self, http): self._http = http; self.user = {"id": "1"}


class FakeCtx:
    channel_id = "555"


def make():
    http = FakeHttp()
    cog = owo_cog.OwoFarm(FakeBot(http))
    out = []

    async def aprint(ctx, title, lines, delay=15): out.append((title, lines))
    async def asuccess(ctx, msg, delay=15): out.append(("ok", msg))
    async def aerror(ctx, msg, delay=15): out.append(("err", msg))
    async def awarn(ctx, msg, delay=15): out.append(("warn", msg))
    cog.aprint, cog.asuccess, cog.aerror, cog.awarn = aprint, asuccess, aerror, awarn
    return cog, http, out


def run(coro): return asyncio.run(coro)


class OwoFarmTests(unittest.TestCase):
    def test_once_sends_commands_in_order(self):
        cog, http, _ = make()
        cog.cfg["cmd_gap"] = 0
        async def go():
            await cog.owofarm(FakeCtx(), value="channel")
            await cog.owofarm(FakeCtx(), value="once")
        run(go())
        self.assertEqual([c[2]["json"]["content"] for c in http.calls], ["wh", "wb"])
        self.assertEqual(http.calls[0][1], "/channels/555/messages")

    def test_start_requires_channel(self):
        cog, http, out = make()
        run(cog.owofarm(FakeCtx(), value="start"))
        self.assertEqual(out[-1][0], "err")
        self.assertFalse(cog.running)

    def test_loop_runs_and_stops(self):
        cog, http, _ = make()
        cog.cfg.update(channel_id="9", cmd_gap=0, delay_min=0.01, delay_max=0.02)
        async def go():
            await cog.owofarm(FakeCtx(), value="start")
            await asyncio.sleep(0.1)
            self.assertTrue(cog.running)
            await cog.owofarm(FakeCtx(), value="stop")
            await asyncio.sleep(0.01)
            return cog.running
        self.assertFalse(run(go()))
        self.assertGreaterEqual(cog.cycles, 2)

    def test_captcha_stops_loop(self):
        cog, http, _ = make()
        cog.cfg.update(channel_id="9", cmd_gap=0, delay_min=0.01, delay_max=0.02)
        async def go():
            await cog.owofarm(FakeCtx(), value="start")
            await asyncio.sleep(0.03)
            await cog.on_message_create({
                "author": {"id": owo_cog.OWO_BOT_ID}, "channel_id": "9",
                "guild_id": "1", "content": "Please complete this captcha",
            })
            await asyncio.sleep(0.01)
            return cog.running
        self.assertFalse(run(go()))

    def test_other_users_do_not_stop_loop(self):
        cog, http, _ = make()
        cog.cfg.update(channel_id="9", cmd_gap=0, delay_min=0.01, delay_max=0.02)
        async def go():
            await cog.owofarm(FakeCtx(), value="start")
            await asyncio.sleep(0.03)
            await cog.on_message_create({
                "author": {"id": "42"}, "channel_id": "9", "guild_id": "1", "content": "captcha",
            })
            running = cog.running
            await cog.owofarm(FakeCtx(), value="stop")
            return running
        self.assertTrue(run(go()))

    def test_edit_commands(self):
        cog, _, _ = make()
        async def go():
            await cog.owofarm(FakeCtx(), value="add owo")
            await cog.owofarm(FakeCtx(), value="up 3")
            await cog.owofarm(FakeCtx(), value="remove 1")
            await cog.owofarm(FakeCtx(), value="delay 5 8 1")
        run(go())
        self.assertEqual(cog.cfg["commands"], ["owo", "wb"])
        self.assertEqual((cog.cfg["delay_min"], cog.cfg["delay_max"], cog.cfg["cmd_gap"]), (5.0, 8.0, 1.0))

    def test_defaults_not_shared_between_instances(self):
        a, _, _ = make()
        b, _, _ = make()
        a.cfg["commands"].append("x")
        self.assertNotIn("x", b.cfg["commands"])
        self.assertNotIn("x", owo_cog.DEFAULTS["commands"])


if __name__ == "__main__":
    unittest.main()
