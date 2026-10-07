import asyncio, os, sys, types, unittest
from unittest.mock import AsyncMock, patch

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
import nitro_cog, giveaway_cog  # noqa: E402


class FakeHttp:
    def __init__(self, fail=None): self.calls, self.fail = [], fail
    async def request(self, route, **kw):
        self.calls.append((route.method, route.path, kw))
        if self.fail: raise RuntimeError(self.fail)
        return {"subscription_plan": {"name": "Nitro"}}


class FakeBot:
    def __init__(self, http): self._http = http; self.user = {"id": "1"}


def run(coro): return asyncio.run(coro)


class NitroTests(unittest.TestCase):
    def test_bare_command_shows_usage_instead_of_stats(self):
        cog = nitro_cog.Nitro(FakeBot(FakeHttp()))
        ctx = object()
        with patch.object(nitro_cog, "send_temp", new_callable=AsyncMock) as send_temp:
            run(cog.nitro(ctx))

        send_temp.assert_awaited_once()
        self.assertIs(send_temp.await_args.args[0], ctx)
        self.assertIn("nitro", send_temp.await_args.args[1].lower())
        self.assertNotIn("nitro_status", send_temp.await_args.args[1].lower())

    def test_extracts_links_and_contextual_codes(self):
        self.assertEqual(nitro_cog.extract_codes("https://discord.gift/AbCdEfGhIjKlMnOp"), ["AbCdEfGhIjKlMnOp"])
        self.assertEqual(nitro_cog.extract_codes("hello AbCdEfGhIjKlMnOp"), [])
        self.assertEqual(nitro_cog.extract_codes("free nitro AbCdEfGhIjKlMnOp"), ["AbCdEfGhIjKlMnOp"])

    def test_claims_once_and_ignores_when_disabled(self):
        http = FakeHttp(); cog = nitro_cog.Nitro(FakeBot(http))
        msg = {"content": "discord.gift/AbCdEfGhIjKlMnOp", "author": {"id": "2", "username": "x"}}
        run(cog.on_message_create(msg)); self.assertEqual(http.calls, [])
        cog.enabled = True
        run(cog.on_message_create(msg)); run(cog.on_message_create(msg))
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.calls[0][1], "/entitlements/gift-codes/AbCdEfGhIjKlMnOp/redeem")
        s = cog.get_stats(); self.assertEqual((s["claimed"], s["cached"], s["last_claimed"]), (1, 1, "x"))
        self.assertEqual(cog.clear_codes(), 1)

    def test_failure_counts(self):
        cog = nitro_cog.Nitro(FakeBot(FakeHttp(fail="Unknown Gift Code"))); cog.enabled = True
        run(cog.on_message_create({"content": "discord.gift/AbCdEfGhIjKlMnOp", "author": {"id": "2"}}))
        self.assertEqual(cog.stats["invalid"], 1)


class GiveawayTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeHttp(); self.cog = giveaway_cog.Giveaway(FakeBot(self.http)); self.cog.enabled = True

    def test_button_entry(self):
        msg = {"id": "9", "channel_id": "5", "guild_id": "4", "content": "🎉 Giveaway! Prize: x",
               "author": {"id": "7", "bot": True},
               "components": [{"type": 1, "components": [{"type": 2, "custom_id": "gw_enter", "label": "Enter"}]}]}
        run(self.cog.on_message_create(msg)); run(self.cog.on_message_create(msg))
        self.assertEqual([c[1] for c in self.http.calls], ["/interactions"])
        self.assertEqual(self.http.calls[0][2]["json"]["data"]["custom_id"], "gw_enter")
        self.assertEqual(self.cog.stats["entered"], 1)

    def test_v2_components_detect_giveaway_and_extract_all_entry_emojis(self):
        msg = {
            "id": "10", "channel_id": "5", "guild_id": "4",
            "author": {"id": "7", "bot": True},
            "components": [{
                "type": 17,
                "components": [{
                    "type": 9,
                    "components": [{
                        "type": 10,
                        "content": "Giveaway! React with 🫶🏽 or <:entry:123456789012345678> to enter.",
                    }],
                    "accessory": {
                        "type": 2, "label": "Enter", "custom_id": "giveaway:enter",
                    },
                }],
            }],
        }
        run(self.cog.on_message_create(msg))
        self.assertEqual(self.http.calls[0][1], "/interactions")
        self.assertEqual(self.cog.stats["entered"], 1)

    def test_v2_reaction_instructions_accept_unicode_and_custom_emoji(self):
        msg = {
            "id": "13", "channel_id": "5", "guild_id": "4",
            "author": {"id": "7", "bot": True},
            "components": [{
                "type": 17,
                "components": [{
                    "type": 10,
                    "content": (
                        "🎁 Giveaway! React with 🫶🏽 or "
                        "<:entry:123456789012345678> to enter."
                    ),
                }],
            }],
        }
        run(self.cog.on_message_create(msg))
        self.assertEqual(
            [call[1] for call in self.http.calls],
            [
                "/channels/5/messages/13/reactions/%F0%9F%AB%B6%F0%9F%8F%BD/@me",
                "/channels/5/messages/13/reactions/entry:123456789012345678/@me",
            ],
        )
        self.assertEqual(self.cog.stats["entered"], 1)

    def test_message_update_can_add_giveaway_content_and_components(self):
        created = {
            "id": "11", "channel_id": "5", "guild_id": "4",
            "author": {"id": "7", "bot": True}, "content": "Please wait...",
        }
        updated = {
            "id": "11",
            "components": [{
                "type": 17,
                "components": [{
                    "type": 10,
                    "content": "Giveaway! Click to enter.",
                }, {
                    "type": 2, "label": "Enter", "custom_id": "giveaway:enter",
                }],
            }],
        }
        run(self.cog.on_message_create(created))
        self.assertEqual(self.http.calls, [])
        run(self.cog.on_message_update(updated))
        self.assertEqual(self.http.calls[0][1], "/interactions")
        self.assertEqual(self.cog.stats["entered"], 1)

    def test_reaction_fallback_and_non_bot_ignored(self):
        bot_msg = {"id": "9", "channel_id": "5", "content": "Giveaway! react with 🎉", "author": {"id": "7", "bot": True}}
        run(self.cog.on_message_create(bot_msg))
        self.assertEqual(self.http.calls[0][0:2], ("PUT", "/channels/5/messages/9/reactions/%F0%9F%8E%89/@me"))
        self.http.calls.clear()
        run(self.cog.on_message_create({**bot_msg, "id": "10", "author": {"id": "8"}}))
        self.assertEqual(self.http.calls, [])

    def test_win_detection(self):
        run(self.cog.on_message_create({"id": "11", "content": "Congratulations <@1> you won!", "author": {"id": "7"}}))
        self.assertEqual((self.cog.stats["won"], self.cog.get_stats()["last_win"]), (1, "Unknown"))


if __name__ == "__main__":
    unittest.main()
