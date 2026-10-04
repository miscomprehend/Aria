import unittest
from unittest.mock import Mock

from giveaway import GiveawaySniper
from nitro import NitroSniper
from api_client import DiscordAPIClient


class NitroGiveawayIntegrationTests(unittest.TestCase):
    def test_nitro_sniper_uses_api_redeem_helper_when_available(self):
        api = Mock()
        api.redeem_gift_code.return_value = Mock(status_code=400, json=Mock(return_value={}))
        sniper = NitroSniper(api)

        sniper._claim_code_fast("abcdefghijklmnop", {"author": {"id": "1", "username": "u"}, "channel_id": "2"})

        api.redeem_gift_code.assert_called_once_with("abcdefghijklmnop")
        api.request.assert_not_called()

    def test_giveaway_button_uses_api_click_button(self):
        api = Mock()
        api.click_button.return_value = True
        sniper = GiveawaySniper(api)
        message = {
            "id": "100",
            "guild_id": "200",
            "channel_id": "300",
            "application_id": "400",
            "flags": 0,
        }
        button = {"custom_id": "enter", "type": 2}

        result = sniper._click_button(message, button)

        self.assertTrue(result)
        api.click_button.assert_called_once_with("200", "300", "100", "400", "enter", 0)

    def test_giveaway_reactions_use_api_add_reaction_with_decoded_emoji(self):
        api = Mock()
        api.add_reaction.return_value = True
        sniper = GiveawaySniper(api)
        message = {"id": "100", "channel_id": "300"}

        result = sniper._add_reactions(message, ["%F0%9F%8E%89"])

        self.assertTrue(result)
        api.add_reaction.assert_called_once_with("300", "100", "🎉")

    def test_api_client_redeem_gift_code_uses_store_referer(self):
        client = object.__new__(DiscordAPIClient)
        client.request = Mock(return_value=Mock(status_code=200))

        response = DiscordAPIClient.redeem_gift_code(client, "giftcode")

        self.assertEqual(response.status_code, 200)
        client.request.assert_called_once_with(
            "POST",
            "/entitlements/gift-codes/giftcode/redeem",
            data={},
            headers={"referer": "https://discord.com/store"},
        )


if __name__ == "__main__":
    unittest.main()
