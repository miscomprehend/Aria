import asyncio
import os
import unittest

from quest_system.captcha import CaptchaSolver
from quest_system.interface import CaptchaDataFromRequest
import quest_system.captcha as captcha_module


class _FakeNoCaptchaSolver:
    called = 0

    def __init__(self, api_key):
        self.api_key = api_key

    async def hcaptcha(self, sitekey, website_url, options=None):
        _FakeNoCaptchaSolver.called += 1
        return {"gRecaptchaResponse": "nocaptcha-token"}


class _FakeYesCaptchaSolver:
    called = 0

    def __init__(self, api_key):
        self.api_key = api_key

    async def hcaptcha(self, sitekey, website_url, options=None):
        _FakeYesCaptchaSolver.called += 1
        return {"gRecaptchaResponse": "yescaptcha-token"}


class QuestCaptchaSolverTests(unittest.TestCase):
    def setUp(self):
        self.original_no_key = os.environ.get("NOCAPTCHAAI_API_KEY")
        self.original_yes_key = os.environ.get("YES_CAPTCHA_API_KEY")
        self.original_no_solver = captcha_module.NoCaptchaSolver
        self.original_yes_solver = captcha_module.YesCaptchaSolver
        self.original_no_available = captcha_module._nocaptcha_available
        self.original_yes_available = captcha_module._yescaptcha_available

        _FakeNoCaptchaSolver.called = 0
        _FakeYesCaptchaSolver.called = 0
        captcha_module.NoCaptchaSolver = _FakeNoCaptchaSolver
        captcha_module.YesCaptchaSolver = _FakeYesCaptchaSolver
        captcha_module._nocaptcha_available = True
        captcha_module._yescaptcha_available = True

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
        captcha_module._nocaptcha_available = self.original_no_available
        captcha_module._yescaptcha_available = self.original_yes_available

    def test_prefers_nocaptcha_when_both_keys_are_set(self):
        os.environ["NOCAPTCHAAI_API_KEY"] = "nocaptcha-key"
        os.environ["YES_CAPTCHA_API_KEY"] = "yes-key"
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
        solver = CaptchaSolver()

        result = asyncio.run(
            solver.solve_captcha(CaptchaDataFromRequest("sitekey", "rqdata"))
        )

        self.assertEqual(result, "yescaptcha-token")
        self.assertEqual(_FakeNoCaptchaSolver.called, 0)
        self.assertEqual(_FakeYesCaptchaSolver.called, 1)

    def test_raises_when_no_provider_is_available(self):
        os.environ.pop("NOCAPTCHAAI_API_KEY", None)
        os.environ.pop("YES_CAPTCHA_API_KEY", None)
        solver = CaptchaSolver()

        with self.assertRaises(ValueError):
            asyncio.run(
                solver.solve_captcha(CaptchaDataFromRequest("sitekey", "rqdata"))
            )


if __name__ == "__main__":
    unittest.main()
