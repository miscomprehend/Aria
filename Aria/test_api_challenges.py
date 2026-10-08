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
    client._dead_captcha_token = ""
    client._last_captcha_token = ""
    client._last_captcha_token_at = 0.0
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
        # No actual captcha solving here (challenge is missing a sitekey), so
        # the TLS transport must NOT be rotated.
        client.header_spoofer.rotate_profile.assert_not_called()
        client.header_spoofer.rebuild_session.assert_not_called()

        self.assertIsNone(client.request("POST", "/channels/456/messages", data={"content": "later"}))
        client.header_spoofer.session.post.assert_called_once()

    def test_403_captcha_challenge_rotates_headers_before_solving(self):
        challenge = Mock()
        challenge.status_code = 403
        challenge.headers = {}
        challenge.json.return_value = {"captcha_sitekey": "site-key"}
        client = make_client(challenge)

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/users/@me/settings", data={"status": "online"})

        self.assertIs(response, challenge)
        self.assertTrue(client.verification_blocked)
        # One attempt + one header-rotation bypass retry: the token must
        # never be hammered with repeated hits on the same challenge.
        self.assertEqual(client.header_spoofer.session.post.call_count, 2)
        # One rotation for the bypass retry; the pre-solve rotation is
        # light (session rebuild only, no new profile).
        self.assertEqual(client.header_spoofer.rotate_profile.call_count, 1)
        client.header_spoofer.rebuild_session.assert_called()

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

    def _drive_challenge_retry(self, status_code, solved_token, side_effect=None):
        """Return ``(client, response)`` after driving one captcha challenge.

        ``make_client`` wires the session to replay a single pending response
        for every call; for a challenge flow we need the first POST to be the
        challenge and the solved retry to be its own response.
        """
        challenge = Mock()
        challenge.status_code = status_code
        challenge.headers = {}
        challenge.json.return_value = {"captcha_sitekey": "site-key"}
        success = Mock()
        success.status_code = 200
        success.headers = {}
        success.json.return_value = {"ok": True}

        client = make_client(challenge)
        client.header_spoofer.session.post.side_effect = side_effect or [challenge, success]
        client.header_spoofer.rotate_profile = Mock()
        client._solve_captcha_challenge = Mock(return_value=solved_token)
        return client, success

    def test_rejected_solved_token_is_quarantined_from_cache_reuse(self):
        """A token Discord already refused must never be replayed by the
        cache-reuse branch (the "cached token" death loop)."""
        # First POST returns the challenge, second POST (with the solved
        # token) is refused again by Discord — exactly the log sequence.
        challenge = Mock()
        challenge.status_code = 400
        challenge.headers = {}
        challenge.json.return_value = {"captcha_sitekey": "site-key"}
        rejected = Mock()
        rejected.status_code = 400
        rejected.headers = {}
        rejected.json.return_value = {"captcha_sitekey": "site-key"}

        client, _ = self._drive_challenge_retry(400, "dead-token",
                                                side_effect=[challenge, rejected])

        with patch("api_client.time.sleep"):
            client.request("POST", "/users/@me", data={"global_name": "Aria"})

        # The rejected token must be recorded as dead so the reuse branch
        # skips it on the next challenge instead of replaying it.
        self.assertEqual(getattr(client, "_dead_captcha_token", ""), "dead-token")

    def test_solved_write_clears_pending_verification_pause(self):
        """When the captcha solve is accepted the pause must be lifted so
        later writes aren't wrongly blocked for 5 minutes."""
        client, success = self._drive_challenge_retry(400, "good-token")

        with patch("api_client.time.sleep"):
            response = client.request("POST", "/users/@me", data={"global_name": "Aria"})

        self.assertIs(response, success)
        self.assertFalse(client.verification_blocked)
        self.assertIsNone(client.verification_endpoint)

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
        # Initial request + 1 header-rotation bypass retry on the first enroll.
        self.assertEqual(client.header_spoofer.session.post.call_count, 2)

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
            "protocol": "yescaptcha",
        }])

    def test_native_2captcha_provider_is_used_without_custom_url(self):
        import os

        class Settings:
            def get(self, key, default=None):
                return {
                    "captcha_api_key": "native-key",
                    "captcha_provider": "twocaptcha",
                    "captcha_api_url": "https://2captcha.com",
                }.get(key, default)

        client = make_client(Mock())
        env = {k: v for k, v in os.environ.items()
               if k not in {"NOCAPTCHAAI_API_KEY", "YES_CAPTCHA_API_KEY"}}
        with patch.dict(os.environ, env, clear=True), patch("config.Config", return_value=Settings()):
            providers = client._get_captcha_provider_candidates()

        self.assertEqual(providers, [{
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }])

    def test_native_2captcha_task_uses_in_php_flat_params(self):
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        response = Mock()
        response.status_code = 200
        response.text = "OK|task-123"
        client.session.post.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        task_id = client._create_captcha_task(provider, {
            "sitekey": "discord-site-key",
            "rqdata": "discord-rqdata",
            "website_url": "https://discord.com/channels/@me",
        })

        self.assertEqual(task_id, "task-123")
        client.session.post.assert_called_once_with(
            "https://2captcha.com/in.php",
            data={
                "key": "native-key",
                "method": "hcaptcha",
                "sitekey": "discord-site-key",
                "pageurl": "https://discord.com/channels/@me",
                "userAgent": "Discord client",
                "json": 1,
                "enterprise": 1,
                "version": "enterprise",
                "sentry": True,
                "data": "discord-rqdata",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"},
            timeout=30,
        )

    def test_solver_uses_session_egress_proxy(self):
        """The captcha solver must be handed the exact proxy the Discord
        session submits through, or the IP-bound token is rejected."""
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        client.header_spoofer.session.proxies = {
            "http": "http://user:pass@1.2.3.4:8080",
            "https": "http://user:pass@1.2.3.4:8080",
        }
        response = Mock()
        response.status_code = 200
        response.text = "OK|task-123"
        client.session.post.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        client._create_captcha_task(provider, {"sitekey": "site-key"})

        sent = client.session.post.call_args.kwargs["data"]
        self.assertEqual(sent["proxy"], "user:pass@1.2.3.4:8080")
        self.assertEqual(sent["proxytype"], "HTTP")

    def test_solver_goes_proxyless_when_session_is_not_proxied(self):
        """With no proxy on the session the solver must NOT be handed a proxy
        (solving from one IP and submitting from another breaks the token)."""
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        client.header_spoofer.session.proxies = {}
        response = Mock()
        response.status_code = 200
        response.text = "OK|task-123"
        client.session.post.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        client._create_captcha_task(provider, {"sitekey": "site-key"})

        sent = client.session.post.call_args.kwargs["data"]
        self.assertNotIn("proxy", sent)
        self.assertNotIn("proxytype", sent)

    def test_yescaptcha_solver_uses_session_egress_proxy(self):
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        client.header_spoofer.session.proxies = {"https": "socks5://1.2.3.4:1080"}
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"errorId": 0, "taskId": "yc-1"}
        client.session.post.return_value = response
        provider = {
            "name": "YesCaptcha",
            "base_url": "https://api.yescaptcha.com",
            "client_key": "yes-key",
            "protocol": "yescaptcha",
        }

        client._create_captcha_task(provider, {"sitekey": "site-key"})

        task = client.session.post.call_args.kwargs["json"]["task"]
        self.assertEqual(task["type"], "HCaptchaTask")
        self.assertEqual(task["proxy"], "socks5:1.2.3.4:1080::")

    def test_native_2captcha_result_polls_res_php(self):
        client = make_client(Mock())
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"status": 1, "request": "solved-token"}
        response.text = '{"status": 1, "request": "solved-token"}'
        client.session.get.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        with patch("api_client.time.sleep"):
            token = client._poll_twocaptcha_result(provider, "task-123")

        self.assertEqual(token, "solved-token")
        client.session.get.assert_called_once_with(
            "https://2captcha.com/res.php",
            params={"key": "native-key", "action": "get", "id": "task-123", "json": 1},
            headers={"Accept": "application/json"},
            timeout=30,
        )

    def test_native_2captcha_result_polls_res_php_plain_text_fallback(self):
        client = make_client(Mock())
        response = Mock()
        response.status_code = 200
        response.json.side_effect = ValueError("no json")
        response.text = "OK|plain-token"
        client.session.get.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        with patch("api_client.time.sleep"):
            token = client._poll_twocaptcha_result(provider, "task-123")

        self.assertEqual(token, "plain-token")

    def test_native_2captcha_plain_text_submit_parses_task_id(self):
        client = make_client(Mock())
        client.header_spoofer.profile.user_agent = "Discord client"
        response = Mock()
        response.status_code = 200
        response.text = "OK|task-456"
        response.headers = {}
        response.json.side_effect = ValueError("no json")
        client.session.post.return_value = response
        provider = {
            "name": "2Captcha",
            "base_url": "https://2captcha.com",
            "client_key": "native-key",
            "protocol": "twocaptcha",
        }

        task_id = client._create_captcha_task(provider, {
            "sitekey": "discord-site-key",
            "website_url": "https://discord.com/channels/@me",
        })

        self.assertEqual(task_id, "task-456")

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