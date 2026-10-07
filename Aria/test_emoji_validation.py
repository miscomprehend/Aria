import unittest

from utils.general import is_valid_emoji


class EmojiValidationTests(unittest.TestCase):
    def test_accepts_unicode_emojis(self):
        for emoji in ("😭", "😀", "👍🏽", "❤️"):
            with self.subTest(emoji=emoji):
                self.assertTrue(is_valid_emoji(emoji))

    def test_accepts_custom_emojis(self):
        for emoji in (
            "<:custom_name:123456789012345678>",
            "<a:custom_name:123456789012345678>",
        ):
            with self.subTest(emoji=emoji):
                self.assertTrue(is_valid_emoji(emoji))

    def test_rejects_non_emoji_text(self):
        self.assertFalse(is_valid_emoji("notemoji"))
        self.assertFalse(is_valid_emoji(":cry:"))


if __name__ == "__main__":
    unittest.main()
