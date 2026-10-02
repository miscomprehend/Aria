import unittest

from afk_system import AFKSystem


class AFKNoticeTests(unittest.TestCase):
    def setUp(self):
        self.system = AFKSystem()

    def test_default_reason_is_not_duplicated(self):
        self.system.set_afk("user-1")

        self.assertEqual(self.system.build_afk_notice("user-1"), "AFK")

    def test_custom_reason_is_formatted_as_one_afk_line(self):
        self.system.set_afk("user-1", "Working on a project")

        self.assertEqual(self.system.build_afk_notice("user-1"), "AFK Working on a project")

    def test_reason_with_afk_prefix_is_not_repeated(self):
        self.system.set_afk("user-1", "I'm AFK: grabbing lunch")

        self.assertEqual(self.system.build_afk_notice("user-1"), "AFK grabbing lunch")
        self.assertEqual(self.system.get_afk_reason("user-1"), "grabbing lunch")

    def test_multiline_reason_is_normalized(self):
        self.system.set_afk("user-1", "AFK\nback in ten")

        self.assertEqual(self.system.build_afk_notice("user-1"), "AFK back in ten")

    def test_default_enable_confirmation_has_one_afk_label(self):
        self.system.set_afk("user-1")

        self.assertEqual(self.system.build_afk_enabled_notice("user-1"), "> AFK enabled")

    def test_custom_enable_confirmation_omits_duplicate_afk_prefix(self):
        self.system.set_afk("user-1", "AFK: grabbing lunch")

        self.assertEqual(self.system.build_afk_enabled_notice("user-1"), "> AFK enabled — grabbing lunch")

    def test_clear_confirmation_omits_zero_duration(self):
        self.assertEqual(self.system.build_afk_cleared_notice("0s"), "> Welcome back")

    def test_clear_confirmation_includes_nonzero_duration(self):
        self.assertEqual(self.system.build_afk_cleared_notice("5m"), "> Welcome back — away for 5m")


if __name__ == "__main__":
    unittest.main()