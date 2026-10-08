import base64
import json
import re
import unittest
from unittest.mock import Mock, patch

from header_spoofer import BrowserProfile, HeaderSpoofer


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


class HeaderSpooferProxyTests(unittest.TestCase):
    """The Discord session and the captcha solver must share one egress IP."""

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_active_proxy_applied_to_new_session(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.proxy_manager = Mock()
        spoofer.proxy_manager.get_active_proxy.return_value = "http://user:pass@1.2.3.4:8080"

        spoofer.rebuild_session()

        self.assertEqual(spoofer.session.proxies,
                         {"http": "http://user:pass@1.2.3.4:8080",
                          "https": "http://user:pass@1.2.3.4:8080"})

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_proxy_survives_profile_rotation(self, _fingerprint_mock, _build_mock):
        """rotate_profile() rebuilds the transport; the egress IP must not
        silently fall back to the host's real IP mid-captcha flow."""
        spoofer = HeaderSpoofer()
        spoofer.proxy_manager = Mock()
        spoofer.proxy_manager.get_active_proxy.return_value = "socks5://1.2.3.4:1080"
        spoofer.rebuild_session()
        self.assertEqual(spoofer.session.proxies.get("https"), "socks5://1.2.3.4:1080")

        spoofer.rotate_profile()

        self.assertEqual(spoofer.session.proxies,
                         {"http": "socks5://1.2.3.4:1080",
                          "https": "socks5://1.2.3.4:1080"})

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_no_proxy_configured_leaves_session_proxyless(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.proxy_manager = Mock()
        spoofer.proxy_manager.get_active_proxy.return_value = ""

        spoofer.rebuild_session()

        self.assertEqual(spoofer.session.proxies, {})
        self.assertEqual(spoofer.get_active_proxy(), "")

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_get_active_proxy_is_empty_without_manager(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.proxy_manager = None

        self.assertEqual(spoofer.get_active_proxy(), "")


class HeaderSpooferStabilityTests(unittest.TestCase):
    """Stable fingerprints, matched TLS/UA/super-properties, header rotation."""

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_profiles_built_together_get_independent_locales(self, _fingerprint_mock, _build_mock):
        """Two profiles must not collapse to the same locale when built fast."""
        seen = {BrowserProfile("146.0.0.0").locale for _ in range(25)}
        self.assertGreater(len(seen), 1)

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_profile_locale_is_stable_within_one_session(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        first = spoofer.get_protected_headers(spoofer.token)
        second = spoofer.get_protected_headers(spoofer.token)

        self.assertEqual(first["X-Discord-Locale"], second["X-Discord-Locale"])
        self.assertEqual(first["X-Discord-Timezone"], second["X-Discord-Timezone"])
        self.assertEqual(first["User-Agent"], second["User-Agent"])
        self.assertEqual(first["X-Fingerprint"], second["X-Fingerprint"])

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_super_properties_match_user_agent_and_build(self, _fingerprint_mock, _build_mock):
        """TLS/UA/X-Super-Properties must describe the SAME browser."""
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        headers = spoofer.get_protected_headers(spoofer.token)
        props = json.loads(base64.b64decode(headers["X-Super-Properties"]).decode())

        self.assertEqual(props["browser_user_agent"], headers["User-Agent"])
        self.assertEqual(props["browser_user_agent"], spoofer.profile.user_agent)
        self.assertEqual(props["browser_version"], spoofer.profile.browser_version)
        self.assertEqual(str(props["client_build_number"]), str(spoofer.build_number))
        self.assertIn(spoofer.profile.browser_version.split(".")[0], headers["Sec-Ch-Ua"])

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_tls_impersonation_major_matches_user_agent_major(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        chosen = spoofer._choose_tls_impersonation()
        profile_major = spoofer.profile.browser_version.split(".")[0]

        self.assertTrue(chosen.startswith("chrome"))
        self.assertEqual(chosen[len("chrome"):], profile_major)

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_header_order_rotates_but_set_is_identical(self, _fingerprint_mock, _build_mock):
        """Same header SET every call, different byte ORDER; UA stays first."""
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        orders = []
        for _ in range(10):
            items = spoofer._build_header_items("fp.123", "locale=en-US")
            orders.append([name for name, _ in spoofer._rotate_header_order(items)])

        first_set = set(orders[0])
        for order in orders[1:]:
            self.assertEqual(set(order), first_set)
        self.assertTrue(all(order[0] == "Authorization" for order in orders))
        self.assertGreater(len({tuple(order) for order in orders}), 1)

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_rotate_does_not_touch_global_random(self, _fingerprint_mock, _build_mock):
        """Spoofer randomness must not perturb the caller's global RNG stream."""
        import random as global_random

        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")

        global_random.seed(1234)
        expected = [global_random.random() for _ in range(3)]

        global_random.seed(1234)
        spoofer.get_protected_headers(spoofer.token)
        spoofer.rotate_profile()
        spoofer.wait_for_slot()
        actual = [global_random.random() for _ in range(3)]

        self.assertEqual(actual, expected)

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_set_proxy_pins_manager_and_session_together(self, _fingerprint_mock, _build_mock):
        """set_proxy keeps manager, session, and solver egress on one IP."""
        from proxy_manager import ProxyManager

        spoofer = HeaderSpoofer()
        spoofer.proxy_manager = ProxyManager()

        spoofer.set_proxy("http://user:pass@9.9.9.9:8080")

        self.assertEqual(spoofer.get_active_proxy(), "http://user:pass@9.9.9.9:8080")
        self.assertEqual(spoofer.session.proxies["https"], "http://user:pass@9.9.9.9:8080")

        spoofer.rotate_profile()

        self.assertEqual(spoofer.session.proxies["https"], "http://user:pass@9.9.9.9:8080")
        self.assertEqual(spoofer.get_active_proxy(), "http://user:pass@9.9.9.9:8080")

    @patch("header_spoofer.get_latest_build", return_value=305411)
    @patch.object(HeaderSpoofer, "_fetch_fingerprint", return_value=("fp.123", "locale=en-US"))
    def test_wait_for_slot_enforces_humanized_gap(self, _fingerprint_mock, _build_mock):
        spoofer = HeaderSpoofer()
        spoofer.initialize_with_token("dGVzdA==.x.y")
        spoofer._min_request_gap = 0.05
        spoofer._max_request_gap = 0.10

        first = spoofer.wait_for_slot()
        second = spoofer.wait_for_slot()

        self.assertGreaterEqual(first, 0.0)
        self.assertGreaterEqual(second, 0.04)


if __name__ == "__main__":
    unittest.main()
