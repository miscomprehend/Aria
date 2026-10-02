import unittest

import formatter as fmt
from api_client import DiscordAPIClient
from format_bootstrap import _format_outgoing


class OutboundMessageFormattingTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(DiscordAPIClient)

    def test_normalizer_preserves_quote_and_bold_markdown(self):
        content = "> **AFK** **I'm at lunch**"

        self.assertEqual(self.client._normalize_outbound_text(content), content)

    def test_global_command_formatter_keeps_quote_prefix(self):
        content = _format_outgoing("> **Status** :: AFK enabled — at lunch")

        self.assertTrue(content.startswith("> "))
        self.assertEqual(self.client._normalize_outbound_text(content), content)

    def test_plain_authored_messages_are_not_automatically_quoted(self):
        content = "A user-authored message for another channel"

        self.assertEqual(self.client._normalize_outbound_text(content), content)

    def test_quote_block_formats_multiline_command_results(self):
        content = fmt.quote_block("first result\nsecond result")

        self.assertEqual(content, "> first result\n> second result")
        self.assertEqual(self.client._normalize_outbound_text(content), content)


if __name__ == "__main__":
    unittest.main()