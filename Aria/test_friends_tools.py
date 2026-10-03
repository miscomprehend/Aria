import unittest
from types import SimpleNamespace

from friends_tools import FriendsTools, setup_friends_tools


class FakeApi:
    def __init__(self, response=None):
        self.response = response or SimpleNamespace(status_code=200, json=lambda: [])
        self.requests = []
        self.messages = []

    def request(self, method, endpoint, **kwargs):
        self.requests.append((method, endpoint, kwargs))
        return self.response

    def send_message(self, channel_id, content):
        self.messages.append((channel_id, content))
        return {"id": "message"}


class FriendToolsTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.tools = FriendsTools(self.api)

    def test_friend_commands_validate_and_use_one_user_id(self):
        self.assertIn("numeric user ID", self.tools.add_friend("not-an-id"))
        self.assertIn("Friend request sent", self.tools.add_friend("<@!12345>"))
        self.assertEqual(
            self.api.requests[-1],
            ("PUT", "/users/@me/relationships/12345", {"data": {}}),
        )
        self.assertIn("Removed friend", self.tools.remove_friend("12345"))
        self.assertEqual(self.api.requests[-1][0:2], ("DELETE", "/users/@me/relationships/12345"))

    def test_relationship_lists_filter_by_type_and_user(self):
        self.api.response = SimpleNamespace(
            status_code=200,
            json=lambda: [
                {"type": 3, "user": {"id": "12", "username": "incoming"}},
                {"type": 4, "user": {"id": "13", "username": "outgoing"}},
            ],
        )
        self.assertEqual(self.tools.relationship_list(3), ["incoming :: 12"])
        self.assertEqual(self.tools.relationship_list(4), ["outgoing :: 13"])

    def test_auto_reply_is_targeted_and_skips_self_and_bots(self):
        self.assertIn("Auto-reply enabled", self.tools.configure_autoreply("1234 Hello there"))
        self.tools.on_message_create(
            {"author": {"id": "1234"}, "channel_id": "channel"},
            owner_id="9999",
        )
        self.tools.on_message_create(
            {"author": {"id": "9999"}, "channel_id": "channel"},
            owner_id="9999",
        )
        self.tools.on_message_create(
            {"author": {"id": "1234", "bot": True}, "channel_id": "channel"},
            owner_id="9999",
        )
        self.assertEqual(self.api.messages, [("channel", "Hello there")])
        self.assertIn("Auto-reply disabled", self.tools.stop_autoreply("1234"))
        self.assertEqual(len(self.api.messages), 1)

    def test_commands_are_registered_and_owner_gated(self):
        class DummyBot:
            def __init__(self):
                self.api = self_api
                self.prefix = ";"
                self.commands = {}

            def command(self, name=None, aliases=None):
                def register(function):
                    self.commands[name or function.__name__] = function
                    for alias in aliases or []:
                        self.commands[alias] = function
                    return function
                return register

        self_api = self.api
        bot = DummyBot()
        setup_friends_tools(bot, lambda user_id: user_id == "owner")
        for name in ("friend", "unfriend", "pending", "outgoing", "blocked", "autoreply", "autoreplystop", "friendlink"):
            self.assertIn(name, bot.commands)

        bot.commands["friend"]({"author_id": "other", "api": self.api, "channel_id": "c"}, ["1234"])
        self.assertEqual(self.api.requests, [])
        self.assertIn("Owner/Admin only", self.api.messages[-1][1])


if __name__ == "__main__":
    unittest.main()
