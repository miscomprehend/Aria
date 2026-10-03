import unittest
from types import SimpleNamespace

from group_chat_tools import GroupChatTools, setup_group_chat_tools


class FakeApi:
    def __init__(self, channel=None, status=200):
        self.channel = channel or {"id": "42", "type": 3, "recipients": []}
        self.status = status
        self.requests = []
        self.messages = []

    def request(self, method, endpoint, **kwargs):
        self.requests.append((method, endpoint, kwargs))
        if endpoint == "/channels/42":
            return SimpleNamespace(status_code=self.status, json=lambda: self.channel)
        return SimpleNamespace(status_code=204, json=lambda: {})

    def send_message(self, channel_id, content):
        self.messages.append((channel_id, content))


class GroupChatToolsTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.tools = GroupChatTools(self.api)

    def test_member_actions_are_single_target_and_require_group_channel(self):
        self.assertIn("numeric user ID", self.tools.change_member("42", "not-an-id", True))
        self.assertIn("Added 123", self.tools.change_member("42", "<@123>", True))
        self.assertEqual(
            self.api.requests[-1],
            ("PUT", "/channels/42/recipients/123", {"data": {}}),
        )

        self.api.channel["recipients"] = [{"id": "456"}]
        self.assertIn("Removed 456", self.tools.change_member("42", "456", False))
        self.assertEqual(
            self.api.requests[-1],
            ("DELETE", "/channels/42/recipients/456", {"data": None}),
        )

        self.api.channel["type"] = 1
        self.assertIn("only works in a group DM", self.tools.get_icon("42"))

    def test_commands_are_owner_gated(self):
        class DummyBot:
            def __init__(self, api):
                self.api = api
                self.prefix = ";"
                self.commands = {}

            def command(self, name=None, aliases=None):
                def register(function):
                    self.commands[name or function.__name__] = function
                    return function
                return register

        bot = DummyBot(self.api)
        setup_group_chat_tools(bot, lambda user_id: user_id == "owner")
        self.assertTrue({"gcicon", "setgcicon", "gcadd", "gcremove"} <= bot.commands.keys())
        bot.commands["gcadd"]({"author_id": "guest", "api": self.api, "channel_id": "42"}, ["123"])
        self.assertEqual(self.api.requests, [])
        self.assertIn("Owner/Admin only", self.api.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
