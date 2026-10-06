import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot import DiscordBot
from main_cog_adapter import install_cog_commands, merge_cog_help_pages


class _Spoofer:
    def get_protected_headers(self, *args, **kwargs):
        return {}


class _API:
    token = "test-token"
    header_spoofer = _Spoofer()

    def __init__(self):
        self.sent = []
        self.requests = []

    def send_message(self, channel_id, content, **kwargs):
        self.sent.append((str(channel_id), content))
        return {"id": "9001", "channel_id": str(channel_id)}

    def request(self, method, endpoint, data=None, **kwargs):
        self.requests.append((method, endpoint, data))
        payload = {}
        if method == "GET" and endpoint == "/users/@me":
            payload = {"id": "42", "username": "test", "global_name": "Test"}
        elif method == "GET" and endpoint.endswith("/profile"):
            payload = {"user_profile": {}}
        return _Response(200, payload)


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class MainCogAdapterTests(unittest.TestCase):
    def setUp(self):
        self.bot = object.__new__(DiscordBot)
        self.bot.api = _API()
        self.bot.prefix = "."
        self.bot.commands = {}
        self.bot.user_id = "42"
        self.bot.session_id = None
        self.bot.ws = None
        self.bot.can_resume = False
        self.bot.command_count = 0
        self.bot._schedule_reconnect = lambda _reason: None

        @self.bot.command(name="logger", aliases=["msglog"])
        def existing_logger(_ctx, _args):
            return None

        @self.bot.command(name="setname", aliases=["legacysetname"])
        def existing_setname(_ctx, _args):
            return None

        @self.bot.command(name="avatar")
        def existing_avatar(_ctx, _args):
            return None

        self.runtime = install_cog_commands(self.bot)
        self.addCleanup(self.runtime.shutdown)

    def test_all_cog_names_and_aliases_resolve_to_cog_adapters(self):
        self.assertEqual(len(self.runtime.cogs), 13)
        self.assertEqual(len(self.runtime.commands), 104)
        for name in self.runtime.commands:
            command = self.bot._resolve_command(name)
            self.assertIsNotNone(command, name)
            self.assertEqual(command.func.__module__, "main_cog_adapter", name)

    def test_cog_replaces_existing_main_command_without_duplicate_registration(self):
        command = self.bot._resolve_command("logger")
        self.assertEqual(command.name, "msglog")
        self.assertEqual(command.func.__module__, "main_cog_adapter")

    def test_cog_alias_replaces_a_main_command_with_the_same_name(self):
        command = self.bot._resolve_command("setname")
        self.assertEqual(command.name, "setdisplayname")
        self.assertEqual(command.func.__module__, "main_cog_adapter")
        self.assertIsNone(self.bot._resolve_command("legacysetname"))

    def test_cog_help_catalog_removes_static_duplicates_and_lists_every_cog_once(self):
        import aria_backend

        pages = {
            "profile": {
                "title": "Profile",
                "lines": [
                    ("setdisplayname <old>", "stale main help"),
                    ("setname <old>", "stale alias help"),
                    ("spotifylyrics [on|off|status]", "stale lyrics help"),
                    ("avatar <url>", "main-only command"),
                ],
            },
            "nitro": {"title": "Nitro", "lines": [("nitro on", "stale sniper help")]},
            "general": {
                "title": "General",
                "lines": [
                    ("setdisplayname <old>", "duplicate profile entry"),
                    ("spotifylyrics [on|off|status]", "duplicate lyrics entry"),
                    ("avatar <user_id>", "duplicate avatar entry"),
                ],
            },
            "friends": {
                "title": "Friends",
                "lines": [("avatar [user_id]", "avatar listed on friends page")],
            },
        }
        category_targets = {
            "profile": "profile",
            "snipers": "nitro",
            "owo": "owo",
        }
        command_help = merge_cog_help_pages(
            pages,
            aria_backend.HELP,
            self.runtime,
            category_targets,
        )

        occurrences = {}
        for page in pages.values():
            for line in page["lines"]:
                if isinstance(line, tuple):
                    name = str(line[0]).split()[0].casefold()
                    occurrences[name] = occurrences.get(name, 0) + 1

        canonical_names = {
            str(command.name).casefold()
            for command in self.runtime.facade._commands
        }
        self.assertTrue(canonical_names.issubset(occurrences))
        self.assertTrue(all(occurrences[name] == 1 for name in canonical_names))
        self.assertEqual(occurrences["setdisplayname"], 1)
        self.assertEqual(occurrences["spotifylyrics"], 1)
        self.assertEqual(occurrences["avatar"], 1)
        self.assertNotIn("setname", occurrences)
        self.assertEqual(occurrences["nitro"], 1)
        self.assertFalse(any(
            str(line[1]).startswith("stale")
            for page in pages.values()
            for line in page["lines"]
            if isinstance(line, tuple) and len(line) == 2
        ))
        self.assertEqual(command_help["setname"]["usage"], "setdisplayname <name>")
        self.assertEqual(command_help["setname"]["category"], "profile")
        self.assertEqual(command_help["spotifylyrics"]["category"], "profile")
        self.assertIn(("spotifylyrics", "Cog command."), pages["profile"]["lines"])
        self.assertIn(("avatar <url>", "main-only command"), pages["profile"]["lines"])
        self.assertNotIn("cogs", pages)
        self.assertIn("general", pages)

    def test_command_executes_cog_callback_and_sends_reply(self):
        self.bot.run_command(
            "uwu",
            {
                "author_id": "42",
                "guild_id": None,
                "channel_id": "123",
                "message_id": "8",
                "content": ".uwu",
                "bot": self.bot,
                "api": self.bot.api,
            },
            [],
        )
        self.assertEqual(len(self.bot.api.sent), 1)
        self.assertIn("UwU", self.bot.api.sent[0][1])

    def test_gateway_events_reach_cog_listeners(self):
        self.runtime.dispatch(
            "MESSAGE_CREATE",
            {
                "id": "1",
                "channel_id": "123",
                "author": {"id": "77", "bot": False},
                "content": "hello",
            },
            wait=True,
        )

    def test_profile_cog_uses_main_api_adapter(self):
        self.bot.run_command(
            "setname",
            {
                "author_id": "42",
                "guild_id": None,
                "channel_id": "123",
                "message_id": "8",
                "content": ".setname Test Name",
                "bot": self.bot,
                "api": self.bot.api,
            },
            ["Test", "Name"],
        )
        self.assertIn(
            ("PATCH", "/users/@me", {"global_name": "Test Name"}),
            self.bot.api.requests,
        )


if __name__ == "__main__":
    unittest.main()
