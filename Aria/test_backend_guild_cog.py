import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch

from aria_backend import ansi


def _load_guild_cog():
    modifyself = types.ModuleType("modifyself")
    modifyself.__path__ = []
    commands = types.ModuleType("modifyself.commands")
    commands.__path__ = []
    http = types.ModuleType("modifyself.http")
    http.__path__ = []
    cog_module = types.ModuleType("modifyself.commands.cog")
    core_module = types.ModuleType("modifyself.commands.core")
    route_module = types.ModuleType("modifyself.http.route")

    class Cog:
        def __init__(self, bot):
            self.bot = bot

    def command(*, name=None, aliases=None):
        return lambda function: function

    class Route:
        def __init__(self, method, path):
            self.method = method
            self.path = path

    cog_module.Cog = Cog
    cog_module.listener = lambda: (lambda function: function)
    core_module.command = command
    route_module.Route = Route
    ascii_helper = types.ModuleType("ascii_helper")
    ascii_helper.send_temp = None
    modules = {
        "modifyself": modifyself,
        "modifyself.commands": commands,
        "modifyself.commands.cog": cog_module,
        "modifyself.commands.core": core_module,
        "modifyself.http": http,
        "modifyself.http.route": route_module,
        "ansi": ansi,
        "ascii_helper": ascii_helper,
    }
    with patch.dict(sys.modules, modules):
        return importlib.import_module("aria_backend.guild_cog")


class BackendGuildCogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guild_module = _load_guild_cog()

    def test_guild_fetch_errors_are_not_reported_as_empty_servers(self):
        class FailedHttp:
            async def request(self, route, **kwargs):
                raise OSError("gateway unavailable")

        guild = self.guild_module.Guild(types.SimpleNamespace(_http=FailedHttp()))
        with self.assertRaisesRegex(RuntimeError, "gateway unavailable"):
            asyncio.run(guild._guilds())
        self.assertIn("gateway unavailable", asyncio.run(guild.list_block()))

    def test_rotation_rejects_invalid_indexes_and_delay_ranges(self):
        guild = self.guild_module.Guild(types.SimpleNamespace())
        for value in ("0 2", "1 not-an-index", "1 0m", "1 1441m", "1 nanm"):
            with self.subTest(value=value):
                self.assertIn("Usage:", guild.start_rotation(value))
        self.assertNotIn("clone", self.guild_module.COMMANDS_INFO)
        self.assertFalse(hasattr(guild, "do_clone"))


if __name__ == "__main__":
    unittest.main()
