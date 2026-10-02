import unittest
from pathlib import Path

from profile_details import format_public_profile_details


class PublicProfileDetailsTests(unittest.TestCase):
    def test_bio_lookup_command_is_registered(self):
        main_source = (Path(__file__).resolve().parent / "main.py").read_text(encoding="utf-8")

        self.assertIn('@bot.command(name="bio")', main_source)
        self.assertIn('("userinfo [user_id]", "View public account and profile details")', main_source)
        self.assertIn('f"{p}userinfo [user_id]"', main_source)

    def test_formats_available_profile_fields(self):
        self.assertEqual(
            format_public_profile_details({
                "user_profile": {
                    "bio": "  Building Aria\nwith friends  ",
                    "pronouns": " they/them ",
                    "accent_color": 0x3F51B5,
                }
            }),
            ["Bio: Building Aria with friends", "Pronouns: they/them", "Accent: #3F51B5"],
        )

    def test_omits_empty_or_invalid_fields(self):
        self.assertEqual(format_public_profile_details({"user_profile": {"bio": " ", "pronouns": None, "accent_color": -1}}), [])
        self.assertEqual(format_public_profile_details({"user_profile": None}), [])
        self.assertEqual(format_public_profile_details(None), [])


if __name__ == "__main__":
    unittest.main()