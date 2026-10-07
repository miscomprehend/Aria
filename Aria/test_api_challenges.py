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

    def test_nested_captcha_payload_is_extracted_for_profile_updates(self):
        client = make_client(Mock())
        nested = {
            "captcha": {
                "sitekey": "nested-site-key",
                "rqdata": "nested-rqdata",
                "rqtoken": "nested-rqtoken",
                "session_id": "nested-session-id",
            },
            "captcha_key": ["verification required"],
        }

        extracted = client._extract_captcha_challenge(nested)

        self.assertEqual(extracted["sitekey"], "nested-site-key")
        self.assertEqual(extracted["rqdata"], "nested-rqdata")
        self.assertEqual(extracted["rqtoken"], "nested-rqtoken")
        self.assertEqual(extracted["session_id"], "nested-session-id")

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

    def test_unsolved_quest_captcha_pauses_only_quest_writes(self):
        challenge = Mock()
        challenge.status_code = 400
        challenge.headers = {}
        challenge.json.return_value = {"captcha_sitekey": "site-key"}
        listing = Mock()
        listing.status_code = 200
        listing.headers = {}
        client = make_client(challenge)
        client.header_spoofer.session.get.return_value = listing
        client._solve_captcha_challenge = Mock(return_value=None)

        with patch("api_client.time.sleep"):
            first = client.request("POST", "/quests/1/enroll", data={})
            second = client.request("POST", "/quests/2/enroll", data={})
            fetched = client.request("GET", "/quests/@me")

        self.assertIs(first, challenge)
        self.assertIsNone(second)
        self.assertIs(fetched, listing)
        self.assertFalse(client.verification_blocked)
        self.assertEqual(client.header_spoofer.session.post.call_count, 1)

    def test_quest_captcha_retries_with_solution_headers(self):
        challenge = Mock()
        challenge.status_code = 400
        challenge.headers = {}
        challenge.json.return_value = {
            "captcha_sitekey": "site-key",
            "captcha_rqtoken": "rq-token",
            "captcha_session_id": "session-id",
        }
        success = Mock()
        success.status_code = 200
        success.headers = {}
        client = make_client(challenge)
        client.header_spoofer.session.post.side_effect = [challenge, success]
        client._solve_captcha_challenge = Mock(return_value="solved-token")

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/quests/1/enroll", data={})

        self.assertIs(response, success)
        retry_headers = client.header_spoofer.session.post.call_args_list[1].kwargs["headers"]
        self.assertEqual(retry_headers["X-Captcha-Key"], "solved-token")
        self.assertEqual(retry_headers["X-Captcha-Rqtoken"], "rq-token")
        self.assertEqual(retry_headers["X-Captcha-Session-Id"], "session-id")

    def test_yescaptcha_key_from_config_is_used_for_solving(self):
        import os

        class Settings:
            def get(self, key, default=None):
                return {"yes_captcha_api_key": "yes-config-key"}.get(key, default)

        client = make_client(Mock())
        env = {k: v for k, v in os.environ.items()
               if k not in {"NOCAPTCHAAI_API_KEY", "YES_CAPTCHA_API_KEY"}}
        with patch.dict(os.environ, env, clear=True), patch("config.Config", return_value=Settings()):
            providers = client._get_captcha_provider_candidates()

        self.assertEqual([(p["name"], p["client_key"]) for p in providers],
                         [("YesCaptcha", "yes-config-key")])

    def test_2captcha_compatible_provider_uses_configured_url_and_key(self):
        import os

        class Settings:
            def get(self, key, default=None):
                return {
                    "captcha_api_key": "compatible-key",
                    "captcha_provider": "twocaptcha",
                    "captcha_api_url": "https://captcha.example/api",
                }.get(key, default)

        client = make_client(Mock())
        env = {k: v for k, v in os.environ.items()
               if k not in {"NOCAPTCHAAI_API_KEY", "YES_CAPTCHA_API_KEY"}}
        with patch.dict(os.environ, env, clear=True), patch("config.Config", return_value=Settings()):
            providers = client._get_captcha_provider_candidates()

        self.assertEqual(providers, [{
            "name": "2Captcha-compatible provider",
            "base_url": "https://captcha.example/api",
            "client_key": "compatible-key",
        }])

    def test_2captcha_compatible_provider_receives_discord_hcaptcha_task(self):
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"errorId": 0, "taskId": "task-id"}
        client.session.post.return_value = response
        provider = {
            "name": "2Captcha-compatible provider",
            "base_url": "https://captcha.example/api",
            "client_key": "compatible-key",
        }

        task_id = client._create_captcha_task(provider, {
            "sitekey": "discord-site-key",
            "rqdata": "discord-rqdata",
            "website_url": "https://discord.com/channels/@me",
        })

        self.assertEqual(task_id, "task-id")
        client.session.post.assert_called_once_with(
            "https://captcha.example/api/createTask",
            json={
                "clientKey": "compatible-key",
                "task": {
                    "type": "HCaptchaTaskProxyless",
                    "websiteURL": "https://discord.com/channels/@me",
                    "websiteKey": "discord-site-key",
                    "userAgent": "Discord client",
                    "isInvisible": False,
                    "rqdata": "discord-rqdata",
                },
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )

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