import json
import tempfile
import time
import unittest
from pathlib import Path

from owo_commands import setup_owo_commands


class FakeApi:
    def __init__(self):
        self.calls = []

    def send_message(self, channel_id, content):
        self.calls.append((channel_id, content))
        return {"id": str(len(self.calls))}


class FakeBot:
    def __init__(self):
        self.api = FakeApi()
        self.commands = {}

    def command(self, name=None, aliases=None):
        def register(function):
            self.commands[name or function.__name__] = function
            for alias in aliases or []:
                self.commands[alias] = function
            return function

        return register


class OwoCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = str(Path(self.temp_dir.name) / "owo_config.json")
        self.bot = FakeBot()
        setup_owo_commands(self.bot, self.config_path)
        self.ctx = {"api": self.bot.api, "channel_id": "555"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_commands_are_registered_on_primary_bot(self):
        self.assertTrue({"owofarm", "owof", "owo", "uwu"} <= self.bot.commands.keys())

    def test_main_initializes_owo_command_registration(self):
        main_source = Path(__file__).with_name("main.py").read_text(encoding="utf-8")
        self.assertIn("from owo_commands import setup_owo_commands", main_source)
        self.assertIn(
            'setup_owo_commands(bot, os.path.join(config.config_dir, "owo_config.json"))',
            main_source,
        )

    def test_channel_and_once_send_configured_cycle(self):
        self.bot.commands["owofarm"](self.ctx, ["channel", "123"])
        self.bot.commands["owofarm"](self.ctx, ["once"])

        self.assertEqual(
            self.bot.api.calls[1:3],
            [("123", "wh"), ("123", "wb")],
        )
        with open(self.config_path, encoding="utf-8") as config_file:
            saved = json.load(config_file)
        self.assertEqual(saved["channel_id"], "123")
        self.assertEqual(saved["commands"], ["wh", "wb"])

    def test_owo_captcha_warning_stops_the_farm(self):
        self.bot.commands["owofarm"](self.ctx, ["channel", "123"])
        self.bot.commands["owofarm"](self.ctx, ["start"])
        self.bot._owo_on_message_create(
            {
                "author": {"id": "408785106942164992"},
                "channel_id": "123",
                "guild_id": "456",
                "content": "Please complete this captcha.",
            }
        )
        time.sleep(0.05)
        self.bot.commands["owofarm"](self.ctx, ["status"])

        self.assertIn("OwO farm: stopped", self.bot.api.calls[-1][1])


if __name__ == "__main__":
    unittest.main()
