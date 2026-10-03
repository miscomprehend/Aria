import unittest

import formatter
from aria_backend import ansi


class BackendAnsiTests(unittest.TestCase):
    def test_shared_formatting_matches_the_app_formatter(self):
        categories = {"Friends": "Relationship tools", "RPC": "Rich presence"}
        commands = [("friend", "Send a friend request"), ("rpc", "Set presence")]
        self.assertEqual(ansi.header("help"), formatter.header("help"))
        self.assertEqual(ansi.category_list(categories), formatter.category_list(categories))
        self.assertEqual(ansi.command_list(commands), formatter.command_list(commands))
        self.assertEqual(ansi._block("Aria\nReady"), formatter._block("Aria\nReady"))
        self.assertEqual(ansi.success("Ready"), formatter.success("Ready"))
        self.assertEqual(ansi.error("Failed"), formatter.error("Failed"))
        self.assertEqual(ansi.warning("Check"), formatter.warning("Check"))

    def test_help_footer_reports_current_page(self):
        self.assertEqual(ansi.footer_page(";", "Friends", 2, 4), ";help friends | page 2/4")

    def test_restored_status_page_and_layout_helpers_use_aria_styles(self):
        self.assertIn(ansi.GREEN, ansi.success("Ready"))
        self.assertIn(ansi.RED, ansi.error("Failed"))
        self.assertIn(ansi.YELLOW, ansi.warning("Check"))
        self.assertIn("Nitro", ansi.nitro_status("ON", 2, 1))
        self.assertIn("Giveaway", ansi.giveaway_status("ON", 3, 1, 1))
        self.assertIn("friends", ansi.command_page("Friends", [("friend", "Add a friend")], ";help friends"))
        self.assertEqual(ansi.paginate(list(range(12)), 2, 10), (list(range(10, 12)), 2))
        self.assertIn("```ansi", ansi.layout("Aria", "body", "footer"))
        self.assertIn("```ansi", ansi.sections("Aria", "body", "footer"))
        self.assertIn("```ansi", ansi.panel("Aria", "body", "footer"))
        self.assertIn("```ansi", ansi._compose("one", "two"))


if __name__ == "__main__":
    unittest.main()
