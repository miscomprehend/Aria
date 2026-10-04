import unittest
from unittest.mock import Mock, patch

from api_client import DiscordAPIClient


def make_client(response):
    client = object.__new__(DiscordAPIClient)
    client.token = "test-token"
    client.auth_failed = False
    client.verification_blocked = False
    client.verification_endpoint = None
    client.rate_limiter = Mock()
    client.rate_limiter.get_wait_time.return_value = None
    client.rate_limiter.handle_429.return_value = 17.0
    client.header_spoofer = Mock()
    client.header_spoofer.proxy_manager = None
    client.header_spoofer.get_protected_headers.side_effect = lambda *args, **kwargs: {}
    client.header_spoofer.session = Mock()
    client.header_spoofer.session.post.return_value = response
    client.session = Mock()
    client._is_cacheable_get = Mock(return_value=False)
    client._record_latency = Mock()
    client._record_rate_limit_hit = Mock()
    client.health_monitor = None
    client._rate_limit_log_times = {}
    client._get_cached_response = Mock(return_value=None)
    client._captcha_provider_name = None
    return client


class APIChallengeTests(unittest.TestCase):
    def test_verification_challenge_is_returned_without_retry(self):
        challenge = Mock()
        challenge.status_code = 400
        challenge.headers = {}
        challenge.json.return_value = {"captcha_key": ["verification required"]}
        client = make_client(challenge)

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/guilds/123/channels", data={"name": "test"})

        self.assertIs(response, challenge)
        self.assertTrue(client.verification_blocked)
        self.assertEqual(client.verification_endpoint, "/guilds/123/channels")
        client.header_spoofer.session.post.assert_called_once()
        client.header_spoofer.rotate_profile.assert_not_called()

        self.assertIsNone(client.request("POST", "/channels/456/messages", data={"content": "later"}))
        client.header_spoofer.session.post.assert_called_once()

    def test_403_captcha_challenge_blocks_without_header_rotation(self):
        challenge = Mock()
        challenge.status_code = 403
        challenge.headers = {}
        challenge.json.return_value = {"captcha_sitekey": "site-key"}
        client = make_client(challenge)

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/users/@me/settings", data={"status": "online"})

        self.assertIs(response, challenge)
        self.assertTrue(client.verification_blocked)
        client.header_spoofer.session.post.assert_called_once()
        client.header_spoofer.rotate_profile.assert_not_called()

    def test_captcha_challenge_retries_with_solution_headers(self):
        challenge = Mock()
        challenge.status_code = 403
        challenge.headers = {}
        challenge.json.return_value = {
            "captcha_sitekey": "site-key",
            "captcha_rqtoken": "rq-token",
            "captcha_session_id": "session-id",
        }
        success = Mock()
        success.status_code = 200
        success.headers = {}
        success.json.return_value = {"ok": True}

        client = make_client(challenge)
        client.header_spoofer.session.post.side_effect = [challenge, success]
        client._solve_captcha_challenge = Mock(return_value="solved-token")

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/users/@me/settings", data={"status": "online"})

        self.assertIs(response, success)
        self.assertFalse(client.verification_blocked)
        self.assertEqual(client.header_spoofer.session.post.call_count, 2)
        first_call = client.header_spoofer.session.post.call_args_list[0]
        second_call = client.header_spoofer.session.post.call_args_list[1]
        self.assertNotIn("X-Captcha-Key", first_call.kwargs.get("headers", {}))
        self.assertEqual(second_call.kwargs["headers"]["X-Captcha-Key"], "solved-token")
        self.assertEqual(second_call.kwargs["headers"]["X-Captcha-Rqtoken"], "rq-token")
        self.assertEqual(second_call.kwargs["headers"]["X-Captcha-Session-Id"], "session-id")

    def test_429_write_is_returned_without_automatic_replay(self):
        rate_limited = Mock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "17"}
        rate_limited.json.return_value = {"retry_after": 17, "global": True}
        client = make_client(rate_limited)

        with patch("api_client.time.sleep") as sleep:
            response = client.request("POST", "/channels/456/messages", data={"content": "hello"})

        self.assertIs(response, rate_limited)
        client.header_spoofer.session.post.assert_called_once()
        client.rate_limiter.handle_429.assert_called_once_with(
            {"Retry-After": "17"},
            "/channels/456/messages",
            global_rate_limit=True,
            retry_after=17,
        )
        sleep.assert_not_called()
        client._record_rate_limit_hit.assert_called_once()


if __name__ == "__main__":
    unittest.main()