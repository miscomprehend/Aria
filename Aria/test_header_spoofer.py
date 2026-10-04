import re
import unittest
from unittest.mock import patch

from header_spoofer import HeaderSpoofer


class HeaderSpooferTests(unittest.TestCase):
    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_includes_super_properties_hash_and_track_headers(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        headers = spoofer.get_protected_headers(spoofer.token)

        self.assertIn("X-Super-Properties", headers)
        self.assertIn("X-Super-Properties-Hash", headers)
        self.assertIn("X-Track", headers)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{8}", headers["X-Super-Properties-Hash"]))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{32}", headers["X-Track"]))

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_super_properties_hash_is_stable_for_same_profile(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        first = spoofer.get_protected_headers(spoofer.token)["X-Super-Properties-Hash"]
        second = spoofer.get_protected_headers(spoofer.token)["X-Super-Properties-Hash"]

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
