import unittest

from giveaway import GiveawaySniper, extract_entry_emojis


class FakeResponse:
    status_code = 204


class FakeApi:
    user_id = "1"

    def __init__(self):
        self.requests = []

    def request(self, method, endpoint, data=None):
        self.requests.append((method, endpoint, data))
        return FakeResponse()


class GiveawayDetectionTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.sniper = GiveawaySniper(self.api)
        self.sniper.enabled = True

    def test_detects_v2_text_and_nested_accessory_button(self):
        message = {
            "id": "9",
            "channel_id": "5",
            "guild_id": "4",
            "author": {"id": "7", "bot": True},
            "components": [{
                "type": 17,
                "components": [{
                    "type": 9,
                    "components": [{
                        "type": 10,
                        "content": "A giveaway! Click to enter.",
                    }],
                    "accessory": {
                        "type": 2,
                        "label": "Join",
                        "custom_id": "giveaway:join",
                    },
                }],
            }],
        }

        self.assertTrue(self.sniper._is_giveaway(message))
        self.sniper._try_enter(message)
        self.assertEqual(self.api.requests[0][1], "/interactions")
        self.assertEqual(
            self.api.requests[0][2]["data"]["custom_id"],
            "giveaway:join",
        )
        self.assertEqual(self.sniper.stats["entered"], 1)

    def test_extracts_unicode_sequences_and_static_or_animated_custom_emoji(self):
        text = (
            "React with 🫶🏽, 👨‍👩‍👧‍👦, 🇨🇦, 1️⃣, "
            "<:entry_star:123456789012345678> or "
            "<a:entry_dance:223456789012345678> to enter"
        )
        self.assertEqual(
            extract_entry_emojis(text),
            [
                "🫶🏽",
                "👨‍👩‍👧‍👦",
                "🇨🇦",
                "1️⃣",
                "entry_star:123456789012345678",
                "a:entry_dance:223456789012345678",
            ],
        )
        self.assertEqual(extract_entry_emojis("🎁 Giveaway"), ["🎁"])

    def test_uses_all_emojis_from_components_v2_instructions(self):
        message = {
            "content": "",
            "components": [{
                "type": 17,
                "components": [{
                    "type": 10,
                    "content": "React with 🫶🏽 or <:entry:123456789012345678> to enter",
                }],
            }],
        }
        self.assertEqual(
            self.sniper._entry_emoji_from_text(message),
            ["🫶🏽", "entry:123456789012345678"],
        )

    def test_reacts_with_all_unicode_and_custom_entry_emojis(self):
        message = {
            "id": "12",
            "channel_id": "5",
            "guild_id": "4",
            "author": {"id": "7", "bot": True},
            "components": [{
                "type": 10,
                "content": (
                    "Giveaway! React with 🫶🏽 or "
                    "<a:entry_dance:123456789012345678> to enter."
                ),
            }],
        }
        self.sniper._try_enter(message)
        self.assertEqual(
            [request[1] for request in self.api.requests],
            [
                "/channels/5/messages/12/reactions/%F0%9F%AB%B6%F0%9F%8F%BD/@me",
                "/channels/5/messages/12/reactions/entry_dance:123456789012345678/@me",
            ],
        )
        self.assertEqual(self.sniper.stats["entered"], 1)


if __name__ == "__main__":
    unittest.main()
