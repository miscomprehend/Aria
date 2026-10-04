import unittest
from types import SimpleNamespace
from unittest.mock import patch

from group_chat_tools import GroupChatTools, setup_group_chat_tools


class FakeDownloadResponse:
    status_code = 200
    headers = {"Content-Type": "image/png", "Content-Length": "8"}
    content = b"png-data"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.content

    def close(self):
        return None


class FakeApi:
    def __init__(self, channel=None, status=200):
        self.channel = channel or {"id": "42", "type": 3, "recipients": []}
        self.channels = []
        self.relationships = []
        self.status = status
        self.requests = []
        self.external_requests = []
        self.messages = []

    def request(self, method, endpoint, **kwargs):
        self.requests.append((method, endpoint, kwargs))
        if endpoint == "/channels/42":
            return SimpleNamespace(status_code=self.status, json=lambda: self.channel)
        if endpoint == "/users/@me/channels":
            return SimpleNamespace(status_code=self.status, json=lambda: self.channels)
        if endpoint == "/users/@me/relationships":
            return SimpleNamespace(status_code=self.status, json=lambda: self.relationships)
        return SimpleNamespace(status_code=204, json=lambda: {})

    def request_external(self, method, url, **kwargs):
        self.external_requests.append((method, url, kwargs))
        return FakeDownloadResponse()

    def send_message(self, channel_id, content):
        self.messages.append((channel_id, content))


class GroupChatToolsTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.tools = GroupChatTools(self.api)

    def test_member_actions_are_single_target_and_require_group_channel(self):
        self.assertIn("No friend found", self.tools.change_member("42", "not-an-id", True))
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

    def test_member_actions_accept_backend_friend_usernames(self):
        self.api.relationships = [
            {"type": 1, "user": {"id": "123", "username": "FriendName"}},
        ]
        self.assertIn("Added FriendName", self.tools.change_member("42", "friendname", True))
        self.assertEqual(
            self.api.requests[-1][0:2],
            ("PUT", "/channels/42/recipients/123"),
        )
        self.api.channel["recipients"] = [{"id": "123", "username": "FriendName"}]
        self.assertIn("Removed FriendName", self.tools.change_member("42", "friendname", False))
        self.assertEqual(
            self.api.requests[-1][0:2],
            ("DELETE", "/channels/42/recipients/123"),
        )

    def test_set_icon_uses_external_request_boundary(self):
        response = FakeDownloadResponse()
        with patch("requests.get", return_value=response):
            self.tools.set_icon("42", "https://images.example/icon.png")
        self.assertEqual(
            self.api.external_requests,
            [("GET", "https://images.example/icon.png", {"timeout": 10, "stream": True})],
        )

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
        self.assertTrue({
            "gcicon", "setgcicon", "gcadd", "gcremove", "gclockdown",
            "gcantiadd", "gcwhitelist", "gcunwhitelist", "gcremoveall",
            "massgcleave",
        } <= bot.commands.keys())
        bot.commands["gcadd"]({"author_id": "guest", "api": self.api, "channel_id": "42"}, ["123"])
        self.assertEqual(self.api.requests, [])
        self.assertIn("Owner/Admin only", self.api.messages[-1][1])

    def test_security_restores_locked_members_and_blocks_unapproved_additions(self):
        self.api.channel["recipients"] = [{"id": "1"}, {"id": "2"}]
        self.tools.set_lockdown("42", True)
        self.tools.on_channel_recipient_remove({
            "channel_id": "42", "user": {"id": "2"},
        }, current_user_id="1")
        self.assertEqual(
            self.api.requests[-1],
            ("PUT", "/channels/42/recipients/2", {"data": {}}),
        )

        self.tools.set_antiadd("42", True)
        self.tools.on_channel_recipient_add({
            "channel_id": "42", "user": {"id": "3"},
        }, current_user_id="1")
        self.assertEqual(
            self.api.requests[-1],
            ("DELETE", "/channels/42/recipients/3", {}),
        )

    def test_security_whitelist_exempts_member_events(self):
        self.api.channel["recipients"] = [{"id": "1"}, {"id": "2"}]
        self.tools.set_lockdown("42", True)
        self.tools.whitelist("42", "2", add=True)
        request_count = len(self.api.requests)
        self.tools.on_channel_recipient_remove(
            {"channel_id": "42", "user": {"id": "2"}}, current_user_id="1"
        )
        self.assertEqual(len(self.api.requests), request_count)

    def test_bulk_group_actions_require_confirmation(self):
        self.api.channel["recipients"] = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        self.api.user_id = "1"
        self.assertIn("2 members", self.tools.remove_all_members("42"))
        self.api.channels = [{"id": "42", "type": 3}, {"id": "43", "type": 3}]
        self.assertIn("2 group chats", self.tools.mass_leave())
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.api.requests))

    def test_remove_all_refuses_when_current_account_id_is_unknown(self):
        self.api.channel["recipients"] = [{"id": "1"}, {"id": "2"}]
        result = self.tools.remove_all_members("42", confirm=True)
        self.assertIn("could not identify", result.lower())
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.api.requests))


if __name__ == "__main__":
    unittest.main()
