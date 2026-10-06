import importlib.util
import asyncio
import unittest
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot import DiscordBot
from main_cog_adapter import (
    install_cog_commands,
    merge_cog_help_pages,
    visible_help_category_keys,
)


class _Spoofer:
    def get_protected_headers(self, *args, **kwargs):
        return {}


class _API:
    token = "test-token"
    header_spoofer = _Spoofer()

    def __init__(self):
        self.sent = []
        self.requests = []
        self.deleted_messages = []
        self.delete_event = threading.Event()
        self.return_none = False
        self.request_returns_none = False

    def send_message(self, channel_id, content, **kwargs):
        self.sent.append((str(channel_id), content))
        if self.return_none:
            return None
        return {"id": "9001", "channel_id": str(channel_id)}

    def request(self, method, endpoint, data=None, **kwargs):
        self.requests.append((method, endpoint, data))
        if self.request_returns_none:
            return None
        payload = {}
        if method == "GET" and endpoint == "/users/@me":
            payload = {"id": "42", "username": "test", "global_name": "Test"}
        elif method == "GET" and endpoint.endswith("/profile"):
            payload = {"user_profile": {}}
        return _Response(200, payload)

    def edit_profile(self, **fields):
        return self.request("PATCH", "/users/@me", data=fields)

    def edit_profile_details(self, **fields):
        return self.request("PATCH", "/users/@me/profile", data=fields)

    def delete_message(self, channel_id, message_id):
        self.deleted_messages.append((channel_id, message_id))
        self.delete_event.set()
        return True


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

        self.runtime = install_cog_commands(
            self.bot,
            command_authorizer=lambda user_id: user_id == "42",
        )
        self.addCleanup(self.runtime.shutdown)

    def test_all_cog_names_and_aliases_resolve_to_cog_adapters(self):
        self.assertEqual(len(self.runtime.cogs), 13)
        self.assertEqual(len(self.runtime.commands), 111)
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

    def test_profile_picture_aliases_resolve_to_the_cog_command(self):
        for alias in ("setpfp", "setavatar", "spfp", "changepfp"):
            with self.subTest(alias=alias):
                command = self.bot._resolve_command(alias)
                self.assertIsNotNone(command)
                self.assertEqual(command.name, "setpfp")
                self.assertEqual(command.func.__module__, "main_cog_adapter")

    def test_profile_setter_legacy_aliases_resolve_to_canonical_commands(self):
        expected = {
            "setglobalname": "setdisplayname",
            "changename": "setdisplayname",
            "setdn": "setdisplayname",
            "sbanner": "setbanner",
            "changebanner": "setbanner",
        }
        for alias, canonical in expected.items():
            with self.subTest(alias=alias):
                command = self.bot._resolve_command(alias)
                self.assertIsNotNone(command)
                self.assertEqual(command.name, canonical)

    def test_cog_help_catalog_removes_static_duplicates_and_lists_every_cog_once(self):
        help_path = Path(__file__).resolve().parent / "aria_backend" / "aria_backend.py"
        help_spec = importlib.util.spec_from_file_location("aria_backend_help_test", help_path)
        help_module = importlib.util.module_from_spec(help_spec)
        help_spec.loader.exec_module(help_module)

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
            help_module.HELP,
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

    def test_root_help_menu_excludes_command_detail_pages(self):
        pages = {
            "general": {},
            "profile": {},
            "nitro": {},
            "ping": {},
            "purge": {},
            "nitro on": {},
            "cogs": {},
        }
        labels = {
            "general": "General",
            "profile": "Profile",
            "nitro": "Nitro",
            "cogs": "Cog commands",
        }
        self.assertEqual(
            visible_help_category_keys(pages, labels),
            ["general", "profile", "nitro"],
        )

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

    def test_cog_http_shim_deletes_temporary_replies_through_main_api(self):
        import ascii_helper

        async def send_temporary_reply():
            ctx = SimpleNamespace(
                message=SimpleNamespace(delete=self.runtime._ignore_command_delete),
                bot=self.runtime.facade,
                send=self.runtime._make_send("123"),
            )
            await ascii_helper.send_temp(ctx, "temporary reply", delay=1)
            return await asyncio.to_thread(self.bot.api.delete_event.wait, 2)

        future = asyncio.run_coroutine_threadsafe(send_temporary_reply(), self.runtime.loop)
        self.assertTrue(future.result(timeout=3))
        self.assertEqual(self.bot.api.deleted_messages, [("123", "9001")])

    def test_null_send_response_does_not_escape_command_execution(self):
        self.bot.api.return_none = True
        self.bot.api.request_returns_none = True

        @self.bot.command(name="explode")
        def explode(_ctx, _args):
            raise RuntimeError("simulated command failure")

        output = StringIO()
        diagnostics = StringIO()
        with redirect_stdout(output), redirect_stderr(diagnostics):
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
            self.bot.run_command(
                "explode",
                {
                    "author_id": "42",
                    "guild_id": None,
                    "channel_id": "123",
                    "bot": self.bot,
                    "api": self.bot.api,
                },
                [],
            )
            self.bot.run_command(
                "uwu",
                {
                    "author_id": "42",
                    "guild_id": None,
                    "channel_id": "123",
                    "message_id": "9",
                    "content": ".uwu",
                    "bot": self.bot,
                    "api": self.bot.api,
                },
                [],
            )

        self.assertIn(("PATCH", "/users/@me", {"global_name": "Test Name"}), self.bot.api.requests)
        self.assertIn("send() returned no message object", diagnostics.getvalue())
        self.assertIn("API returned no message object", output.getvalue())
        self.assertEqual(self.bot.command_count, 3)
        self.assertTrue(self.runtime.loop.is_running())

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

    def test_profile_details_use_the_dedicated_protected_api_method(self):
        self.bot.run_command(
            "setbio",
            {
                "author_id": "42",
                "guild_id": None,
                "channel_id": "123",
                "message_id": "8",
                "content": ".setbio Profile text",
                "bot": self.bot,
                "api": self.bot.api,
            },
            ["Profile", "text"],
        )
        self.assertIn(
            ("PATCH", "/users/@me/profile", {"bio": "Profile text"}),
            self.bot.api.requests,
        )

    def test_profile_set_commands_patch_the_expected_fields(self):
        commands = (
            ("setdisplayname", ["Aria", "Name"], "global_name", "Aria Name", "/users/@me"),
            ("setbio", ["clear"], "bio", "", "/users/@me/profile"),
            ("setpronouns", ["they/them"], "pronouns", "they/them", "/users/@me/profile"),
            ("setaccent", ["#5b8cff"], "accent_color", 0x5B8CFF, "/users/@me"),
            ("setbanner", ["remove"], "banner", None, "/users/@me"),
        )
        for index, (name, args, field, value, endpoint) in enumerate(commands):
            with self.subTest(command=name):
                self.bot.run_command(
                    name,
                    {
                        "author_id": "42",
                        "guild_id": None,
                        "channel_id": "123",
                        "message_id": str(20 + index),
                        "content": f".{name} {' '.join(args)}",
                        "bot": self.bot,
                        "api": self.bot.api,
                    },
                    args,
                )
                self.assertIn(("PATCH", endpoint, {field: value}), self.bot.api.requests)

    def test_profile_set_commands_retain_owner_admin_restriction(self):
        self.bot.run_command(
            "setbio",
            {
                "author_id": "77",
                "guild_id": None,
                "channel_id": "123",
                "message_id": "8",
                "content": ".setbio unauthorized change",
                "bot": self.bot,
                "api": self.bot.api,
            },
            ["unauthorized", "change"],
        )

        self.assertFalse(any(
            method == "PATCH" and endpoint == "/users/@me/profile"
            for method, endpoint, _data in self.bot.api.requests
        ))
        self.assertIn("Owner/Admin only", self.bot.api.sent[-1][1])

    def test_setpfp_downloads_validated_image_and_patches_current_account(self):
        import profile_cog

        with patch.object(
            profile_cog,
            "download_avatar_data_uri",
            return_value="data:image/png;base64,UE5H",
        ) as download:
            self.bot.run_command(
                "setpfp",
                {
                    "author_id": "42",
                    "guild_id": None,
                    "channel_id": "123",
                    "message_id": "10",
                    "content": ".setpfp https://images.example/avatar.png",
                    "bot": self.bot,
                    "api": self.bot.api,
                },
                ["https://images.example/avatar.png"],
            )

        download.assert_called_once_with("https://images.example/avatar.png")
        self.assertIn(
            ("PATCH", "/users/@me", {"avatar": "data:image/png;base64,UE5H"}),
            self.bot.api.requests,
        )


if __name__ == "__main__":
    unittest.main()
