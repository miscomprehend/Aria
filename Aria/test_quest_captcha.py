import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from quest_system.captcha import CaptchaSolver
from quest_system.constants import Constants
from quest_system.interface import CaptchaDataFromRequest
from quest_system.providers.twocaptcha import TwoCaptchaSolver
from quest_system.providers.yescaptcha import TwoCaptchaCompatibleSolver, YesCaptchaSolver
import quest_system.captcha as captcha_module


class _EmptySettings:
    """Config stub with no captcha keys, isolating tests from the real config.json."""

    def get(self, key, default=None):
        return default


class _FakeNoCaptchaSolver:
    called = 0
    last_call = None

    def __init__(self, api_key):
        self.api_key = api_key

    # NoCaptcha is proxyless-only and does not accept a proxy kwarg.
    async def hcaptcha(self, sitekey, website_url, options=None, rotate=None):
        _FakeNoCaptchaSolver.called += 1
        _FakeNoCaptchaSolver.last_call = (sitekey, website_url, options, rotate)
        return {"gRecaptchaResponse": "nocaptcha-token"}


class _FakeYesCaptchaSolver:
    called = 0
    image_called = 0
    last_call = None

    def __init__(self, api_key):
        self.api_key = api_key

    async def hcaptcha(self, sitekey, website_url, proxy=None, options=None, rotate=None):
        _FakeYesCaptchaSolver.called += 1
        _FakeYesCaptchaSolver.last_call = (sitekey, website_url, options, rotate)
        _FakeYesCaptchaSolver.last_proxy = proxy
        return {"gRecaptchaResponse": "yescaptcha-token"}

    async def image_captcha(self, image_base64):
        _FakeYesCaptchaSolver.image_called += 1
        return {"text": "abcd"}


class _FakeTwoCaptchaCompatibleSolver(_FakeYesCaptchaSolver):
    last_base_url = None

    def __init__(self, api_key, base_url):
        super().__init__(api_key)
        self.provider_name = "2Captcha-compatible provider"
        _FakeTwoCaptchaCompatibleSolver.last_base_url = base_url


class _FakeTwoCaptchaSolver:
    called = 0
    last_key = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.provider_name = "2Captcha"
        _FakeTwoCaptchaSolver.called += 1
        _FakeTwoCaptchaSolver.last_key = api_key

    async def hcaptcha(self, sitekey, website_url, proxy=None, options=None, rotate=None):
        _FakeTwoCaptchaSolver.last_proxy = proxy
        return {"gRecaptchaResponse": "twocaptcha-token"}

    async def image_captcha(self, image_base64, rotate=None):
        return {"text": "wxyz"}


class QuestCaptchaSolverTests(unittest.TestCase):
    def setUp(self):
        self.original_no_key = os.environ.get("NOCAPTCHAAI_API_KEY")
        self.original_yes_key = os.environ.get("YES_CAPTCHA_API_KEY")
        self.original_no_solver = captcha_module.NoCaptchaSolver
        self.original_yes_solver = captcha_module.YesCaptchaSolver
        self.original_twocaptcha_solver = captcha_module.TwoCaptchaCompatibleSolver
        self.original_native_twocaptcha_solver = captcha_module.TwoCaptchaSolver
        self.original_no_available = captcha_module._nocaptcha_available
        self.original_yes_available = captcha_module._yescaptcha_available
        self.original_twocaptcha_available = captcha_module._twocaptcha_compatible_available
        self.original_native_twocaptcha_available = captcha_module._twocaptcha_available

        _FakeNoCaptchaSolver.called = 0
        _FakeNoCaptchaSolver.last_call = None
        _FakeYesCaptchaSolver.called = 0
        _FakeYesCaptchaSolver.image_called = 0
        _FakeYesCaptchaSolver.last_call = None
        _FakeTwoCaptchaSolver.called = 0
        _FakeTwoCaptchaSolver.last_key = None
        captcha_module.NoCaptchaSolver = _FakeNoCaptchaSolver
        captcha_module.YesCaptchaSolver = _FakeYesCaptchaSolver
        captcha_module.TwoCaptchaSolver = _FakeTwoCaptchaSolver
        captcha_module._nocaptcha_available = True
        captcha_module._yescaptcha_available = True
        captcha_module._twocaptcha_compatible_available = True
        captcha_module._twocaptcha_available = True

    def tearDown(self):
        if self.original_no_key is None:
            os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        else:
            os.environ["NOCAPTCHAAI_API_KEY"] = self.original_no_key

        if self.original_yes_key is None:
            os.environ.pop("YES_CAPTCHA_API_KEY", None)
        else:
            os.environ["YES_CAPTCHA_API_KEY"] = self.original_yes_key

        captcha_module.NoCaptchaSolver = self.original_no_solver
        captcha_module.YesCaptchaSolver = self.original_yes_solver
        captcha_module.TwoCaptchaCompatibleSolver = self.original_twocaptcha_solver
        captcha_module.TwoCaptchaSolver = self.original_native_twocaptcha_solver
        captcha_module._nocaptcha_available = self.original_no_available
        captcha_module._yescaptcha_available = self.original_yes_available
        captcha_module._twocaptcha_compatible_available = self.original_twocaptcha_available
        captcha_module._twocaptcha_available = self.original_native_twocaptcha_available

    def test_uses_configured_2captcha_compatible_provider(self):
        class Settings:
            def get(self, key, default=None):
                return {
                    "captcha_api_key": "compatible-key",
                    "captcha_provider": "twocaptcha",
                    "captcha_api_url": "https://captcha.example/api",
                }.get(key, default)

        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        captcha_module.TwoCaptchaCompatibleSolver = _FakeTwoCaptchaCompatibleSolver
        with patch("config.Config", return_value=Settings()):
            solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(CaptchaDataFromRequest("site-key", "rqdata"))
        )

        self.assertEqual(result, "yescaptcha-token")
        self.assertEqual(
            _FakeTwoCaptchaCompatibleSolver.last_base_url,
            "https://captcha.example/api",
        )
        self.assertEqual(_FakeYesCaptchaSolver.called, 1)

    def test_prefers_nocaptcha_when_both_keys_are_set(self):
        os.environ["NOCAPTCHAAI_API_KEY"] = "nocaptcha-key"
        os.environ["YES_CAPTCHA_API_KEY"] = "yes-key"
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(CaptchaDataFromRequest("sitekey", "rqdata"))
        )

        self.assertEqual(result, "nocaptcha-token")
        self.assertEqual(_FakeNoCaptchaSolver.called, 1)
        self.assertEqual(_FakeYesCaptchaSolver.called, 0)

    def test_falls_back_to_yescaptcha_when_nocaptcha_key_missing(self):
        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ["YES_CAPTCHA_API_KEY"] = "yes-key"
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(CaptchaDataFromRequest("sitekey", "rqdata"))
        )

        self.assertEqual(result, "yescaptcha-token")
        self.assertEqual(_FakeNoCaptchaSolver.called, 0)
        self.assertEqual(_FakeYesCaptchaSolver.called, 1)

    def test_passes_sitekey_and_user_agent_to_yescaptcha(self):
        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ["YES_CAPTCHA_API_KEY"] = "yes-key"
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(
                CaptchaDataFromRequest(
                    "site-key",
                    "rqdata",
                    user_agent="Mozilla/5.0 current-browser",
                )
            )
        )

        self.assertEqual(result, "yescaptcha-token")
        sitekey, website_url, options, _ = _FakeYesCaptchaSolver.last_call
        self.assertEqual(sitekey, "site-key")
        self.assertEqual(website_url, "https://discord.com/channels/@me")
        self.assertEqual(options["userAgent"], "Mozilla/5.0 current-browser")

    def test_raises_when_no_provider_is_available(self):
        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        with self.assertRaises(ValueError):
            asyncio.run(
                solver.solve_captcha(CaptchaDataFromRequest("sitekey", "rqdata"))
            )

    def test_solves_image_captcha_with_supported_provider(self):
        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ["YES_CAPTCHA_API_KEY"] = "yes-key"
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        result = asyncio.run(solver.solve_image_captcha("ZmFrZS1pbWFnZQ=="))

        self.assertEqual(result, "abcd")
        self.assertEqual(_FakeYesCaptchaSolver.image_called, 1)

    def test_raises_for_image_captcha_when_provider_does_not_support_it(self):
        os.environ["NOCAPTCHAAI_API_KEY"] = "nocaptcha-key"
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        with patch("config.Config", return_value=_EmptySettings()):
            solver = CaptchaSolver()

        with self.assertRaises(ValueError):
            asyncio.run(solver.solve_image_captcha("ZmFrZS1pbWFnZQ=="))

    def test_uses_native_2captcha_by_default(self):
        class Settings:
            def get(self, key, default=None):
                return {
                    "captcha_api_key": "native-key",
                    "captcha_provider": "twocaptcha",
                    "captcha_api_url": "https://2captcha.com",
                }.get(key, default)

        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        with patch("config.Config", return_value=Settings()):
            solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(CaptchaDataFromRequest("site-key", "rqdata"))
        )

        self.assertEqual(result, "twocaptcha-token")
        self.assertEqual(_FakeTwoCaptchaSolver.called, 1)
        self.assertEqual(_FakeTwoCaptchaSolver.last_key, "native-key")

    def test_solves_image_captcha_with_native_2captcha(self):
        class Settings:
            def get(self, key, default=None):
                return {
                    "captcha_api_key": "native-key",
                    "captcha_provider": "twocaptcha",
                    "captcha_api_url": "https://2captcha.com",
                }.get(key, default)

        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        with patch("config.Config", return_value=Settings()):
            solver = CaptchaSolver()

        result = asyncio.run(solver.solve_image_captcha("ZmFrZS1pbWFnZQ=="))

        self.assertEqual(result, "wxyz")


class YesCaptchaTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_generic_task_preserves_provider_fields(self):
        solver = YesCaptchaSolver("yes-key", max_attempts=1)
        solver.create_task = AsyncMock(return_value={"taskId": "task-id"})
        solver.get_task_result = AsyncMock(
            return_value={"solution": {"gRecaptchaResponse": "solution"}}
        )
        task = {
            "type": "ReCaptchaV3TaskProxyless",
            "websiteURL": "https://example.com",
            "websiteKey": "site-key",
            "pageAction": "submit",
            "userAgent": "Mozilla/5.0 current-browser",
        }

        result = await solver.solve_task(task)

        self.assertEqual(result, {"gRecaptchaResponse": "solution"})
        solver.create_task.assert_awaited_once_with(task)
        self.assertEqual(solver.headers["User-Agent"], Constants.USER_AGENT)

    async def test_2captcha_compatible_solver_uses_configured_base_url(self):
        solver = TwoCaptchaCompatibleSolver(
            "provider-key",
            "https://captcha.example/api/",
            max_attempts=1,
        )
        solver.create_task = AsyncMock(return_value={"taskId": "task-id"})
        solver.get_task_result = AsyncMock(
            return_value={"solution": {"gRecaptchaResponse": "solved-token"}}
        )

        result = await solver.hcaptcha(
            "site-key",
            "https://discord.com/channels/@me",
            options={"rqdata": "challenge-data", "userAgent": "Discord client"},
        )

        self.assertEqual(solver.BASE_URL, "https://captcha.example/api")
        self.assertEqual(result, {"gRecaptchaResponse": "solved-token"})
        solver.create_task.assert_awaited_once_with({
            "type": "HCaptchaTaskProxyless",
            "rqdata": "challenge-data",
            "userAgent": "Discord client",
            "websiteURL": "https://discord.com/channels/@me",
            "websiteKey": "site-key",
        })

    async def test_2captcha_compatible_solver_rejects_non_https_url(self):
        with self.assertRaisesRegex(ValueError, "must be HTTPS"):
            TwoCaptchaCompatibleSolver("provider-key", "http://captcha.example")

    async def test_hcaptcha_forwards_user_agent(self):
        solver = YesCaptchaSolver("yes-key", max_attempts=1)
        solver.create_task = AsyncMock(return_value={"taskId": "task-id"})
        solver.get_task_result = AsyncMock(return_value={"solution": {"token": "ok"}})

        await solver.hcaptcha(
            "site-key",
            "https://example.com",
            options={
                "userAgent": "Mozilla/5.0 current-browser",
            },
        )

        solver.create_task.assert_awaited_once_with(
            {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": "https://example.com",
                "websiteKey": "site-key",
                "userAgent": "Mozilla/5.0 current-browser",
            }
        )


class TwoCaptchaNativeSolverTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_non_https_base_url(self):
        with self.assertRaisesRegex(ValueError, "must be HTTPS"):
            TwoCaptchaSolver("key", base_url="http://2captcha.com")

    def test_rejects_credentials_in_base_url(self):
        with self.assertRaisesRegex(ValueError, "must be HTTPS"):
            TwoCaptchaSolver("key", base_url="https://user:pass@2captcha.com")

    def test_requires_api_key(self):
        with self.assertRaisesRegex(ValueError, "API key is required"):
            TwoCaptchaSolver("")

    async def test_hcaptcha_submits_and_polls_native_api(self):
        solver = TwoCaptchaSolver("test-key", max_attempts=1)
        solver.create_task = AsyncMock(return_value={"taskId": "12345"})
        solver.get_task_result = AsyncMock(return_value={"solution": {"token": "solved-token"}})

        result = await solver.hcaptcha(
            "site-key",
            "https://discord.com/channels/@me",
            options={"rqdata": "challenge-data", "userAgent": "Discord client"},
        )

        self.assertEqual(result, {"gRecaptchaResponse": "solved-token"})
        params = solver.create_task.await_args.args[0]
        self.assertEqual(params["method"], "hcaptcha")
        self.assertEqual(params["sitekey"], "site-key")
        self.assertEqual(params["pageurl"], "https://discord.com/channels/@me")
        self.assertEqual(params["data"], "challenge-data")
        self.assertEqual(params["userAgent"], "Discord client")
        solver.get_task_result.assert_awaited_once_with("12345")

    async def test_image_captcha_uses_base64_method(self):
        solver = TwoCaptchaSolver("test-key", max_attempts=1)
        solver.create_task = AsyncMock(return_value={"taskId": "99"})
        solver.get_task_result = AsyncMock(return_value={"solution": {"token": "abcd"}})

        result = await solver.image_captcha("data:image/png;base64,ZmFrZQ==")

        self.assertEqual(result, {"text": "abcd"})
        params = solver.create_task.await_args.args[0]
        self.assertEqual(params["method"], "base64")
        self.assertEqual(params["body"], "ZmFrZQ==")

    async def test_normalize_response_parses_ok_prefix(self):
        self.assertEqual(TwoCaptchaSolver._normalize_response("OK|9876"), "9876")

    async def test_normalize_response_raises_on_error(self):
        with self.assertRaisesRegex(ValueError, "ERROR_WRONG_USER_KEY"):
            TwoCaptchaSolver._normalize_response("ERROR_WRONG_USER_KEY")


if __name__ == "__main__":
    unittest.main()
