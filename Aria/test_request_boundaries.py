import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from api_client import DiscordAPIClient, RoutedSession
from superreact import SuperReactClient


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return SimpleNamespace(status_code=200)


class RequestBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.client = object.__new__(DiscordAPIClient)
        self.internal_calls = []
        self.external_session = FakeSession()
        self.client.session = RoutedSession(
            self._internal_request,
            external_session=self.external_session,
        )

    def _internal_request(self, method, endpoint, **kwargs):
        self.internal_calls.append((method, endpoint, kwargs))
        return SimpleNamespace(status_code=200)

    def test_external_request_uses_separate_session_and_strips_sensitive_headers(self):
        self.client.request_external(
            "GET",
            "https://cdn.example.test/image.png",
            headers={
                "Authorization": "secret-token",
                "Cookie": "session=secret",
                "User-Agent": "spoofed-client",
                "Sec-CH-UA": "spoofed-client-hints",
                "X-Fingerprint": "discord-fingerprint",
                "Accept": "image/png",
            },
        )

        self.assertEqual(self.internal_calls, [])
        _, _, options = self.external_session.calls[0]
        headers = {key.casefold(): value for key, value in options["headers"].items()}
        self.assertEqual(headers, {"accept": "image/png"})

    def test_routed_session_uses_discord_pipeline_only_for_discord_hosts(self):
        internal_calls = []

        def internal_request(method, endpoint, **kwargs):
            internal_calls.append((method, endpoint, kwargs))
            return SimpleNamespace(status_code=200)

        external_session = FakeSession()
        router = RoutedSession(internal_request, external_session=external_session)
        router.get(
            "https://discord.com/api/v9/users/@me?source=router",
            headers={
                "Authorization": "untrusted-token",
                "User-Agent": "untrusted-client",
                "Sec-CH-UA": "untrusted-hints",
                "Accept": "application/json",
            },
        )
        router.get(
            "https://cdn.discordapp.com/icons/example.png",
            headers={"Authorization": "secret", "Accept": "image/png"},
        )
        router.get(
            "https://discord.com.attacker.example/api/v9/users/@me",
            headers={"Authorization": "secret"},
        )

        self.assertEqual(len(internal_calls), 1)
        self.assertEqual(internal_calls[0][0:2], ("GET", "/users/@me"))
        self.assertEqual(internal_calls[0][2]["params"], {"source": "router"})
        self.assertEqual(internal_calls[0][2]["headers"], {"Accept": "application/json"})
        self.assertEqual(len(external_session.calls), 2)
        for _, _, options in external_session.calls:
            headers = {key.casefold() for key in options["headers"]}
            self.assertNotIn("authorization", headers)

    def test_discord_routed_request_uses_header_spoofer_and_rate_limiter(self):
        response = SimpleNamespace(status_code=200, headers={})
        discord_session = Mock()
        discord_session.get.return_value = response
        rate_limiter = Mock()
        rate_limiter.get_wait_time.return_value = None
        header_spoofer = Mock()
        header_spoofer.session = discord_session
        header_spoofer.get_protected_headers.return_value = {
            "Authorization": "active-account-token",
            "User-Agent": "configured-discord-profile",
        }

        client = object.__new__(DiscordAPIClient)
        client.token = "active-account-token"
        client.header_spoofer = header_spoofer
        client.rate_limiter = rate_limiter
        client.auth_failed = False
        client.verification_blocked = False
        client.health_monitor = None
        client._rate_limit_log_times = {}
        client._is_cacheable_get = Mock(return_value=False)
        client._record_latency = Mock()
        client.session = RoutedSession(client.request)

        result = client.session.get("https://discord.com/api/v9/users/@me")

        self.assertIs(result, response)
        header_spoofer.get_protected_headers.assert_called_once_with("active-account-token")
        rate_limiter.get_wait_time.assert_called_once_with("/users/@me")
        rate_limiter.decrement.assert_called_once_with("/users/@me")
        self.assertEqual(
            discord_session.get.call_args.kwargs["headers"]["Authorization"],
            "active-account-token",
        )

    def test_external_request_rejects_non_https_and_embedded_credentials(self):
        for url in (
            "http://example.test/image.png",
            "https://user:password@example.test/image.png",
            "//example.test/image.png",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.client.request_external("GET", url)
        self.assertEqual(self.external_session.calls, [])

    def test_superreact_uses_shared_discord_api_client(self):
        class FakeDiscordAPI:
            def __init__(self):
                self.calls = []

            def request(self, method, endpoint, **kwargs):
                self.calls.append((method, endpoint, kwargs))
                return SimpleNamespace(status_code=204)

        api = FakeDiscordAPI()
        client = SuperReactClient("unused-token", api)
        client.send_super_reaction_rest(None, "channel", "message", "😀")

        self.assertEqual(api.calls[0][0], "PUT")
        self.assertTrue(api.calls[0][1].startswith("/channels/channel/messages/message/reactions/"))
        self.assertEqual(api.calls[0][2]["params"]["type"], 1)

    def test_token_scoped_request_uses_raw_authorization_value(self):
        class FakeSpoofer:
            def get_protected_headers(self, token):
                return {"Authorization": token, "User-Agent": "configured"}

        self.client.header_spoofer = FakeSpoofer()
        self.client.request = Mock(return_value=SimpleNamespace(status_code=200))
        self.client.request_as_token("GET", "/users/@me", "token-value")

        headers = self.client.request.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "token-value")
        self.assertFalse(headers["Authorization"].startswith("Bearer "))


if __name__ == "__main__":
    unittest.main()
