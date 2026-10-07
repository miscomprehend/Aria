"""Native 2Captcha client for hCaptcha and image captchas.

Unlike ``TwoCaptchaCompatibleSolver`` (which speaks the YesCaptcha task
protocol at a configurable base URL), this client talks to the *real* 2Captcha
HTTP API:

* Submit:  ``GET/POST https://2captcha.com/in.php``  with ``key`` + ``method``
* Poll:    ``GET https://2captcha.com/res.php``       with ``key`` + ``action=get``

2Captcha uses flat query parameters rather than the JSON task envelope used by
YesCaptcha/NoCaptchaAI, so it needs its own submit/poll implementation. The
retry-with-rotation behavior is shared through ``base.RetryMixin``.

Supported challenge kinds:

* ``hcaptcha``      -> ``method=hcaptcha`` (``sitekey``, ``pageurl``, optional ``invisible``)
* ``image_captcha`` -> ``method=base64`` (``body``)

Both accept an optional ``rotate`` callback invoked before every retry so the
caller can rotate the browser/header profile in sync with the fresh task.
"""

import asyncio
from typing import Callable, Dict, Any, Optional

import aiohttp

from .base import RetryMixin


class TwoCaptchaSolver(RetryMixin):
    """Native 2Captcha (2captcha.com) API client for solving captchas."""

    BASE_URL = 'https://2captcha.com'
    provider_name = '2Captcha'

    def __init__(self, api_key: str, base_url: str = '', max_attempts: int = 3):
        """Initialize the 2Captcha solver.

        Args:
            api_key: 2Captcha API key.
            base_url: Optional API base override (must be an HTTPS origin with
                no credentials, query, or fragment). Defaults to 2captcha.com.
            max_attempts: How many fresh tasks to submit when the provider
                reports a retryable error (e.g. ``ERROR_CAPTCHA_UNSOLVABLE``).
        """
        key = str(api_key or '').strip()
        if not key:
            raise ValueError("2Captcha API key is required.")
        self.api_key = key
        self.max_attempts = max(1, int(max_attempts))
        self.session: Optional[aiohttp.ClientSession] = None
        if base_url:
            self.BASE_URL = self._validate_base_url(base_url)

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        from urllib.parse import urlsplit

        parsed = urlsplit(str(base_url or '').strip())
        if (
            parsed.scheme.lower() != 'https'
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Captcha provider API URL must be HTTPS without credentials, query, or fragment."
            )
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    # ── 2Captcha HTTP API ────────────────────
    @staticmethod
    def _normalize_response(text: str) -> str:
        """Return the payload after the leading ``OK|`` marker, else raise."""
        body = str(text or '').strip()
        if body.startswith('OK|'):
            return body[3:]
        if body.startswith('ERROR_'):
            raise ValueError(f"2Captcha error: {body}")
        raise ValueError(f"2Captcha unexpected response: {body[:200]}")

    async def _submit(self, params: Dict[str, Any]) -> str:
        """Submit a task and return its 2Captcha task ID."""
        session = await self._get_session()
        payload = {
            'key': self.api_key,
            'json': 0,
            **params,
        }
        try:
            async with session.post(
                f'{self.BASE_URL}/in.php',
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            ) as resp:
                text = await resp.text()
        except Exception as e:
            raise ValueError(f"Failed to create task: {e}")

        task_id = self._normalize_response(text)
        if not task_id:
            raise ValueError("2Captcha returned an empty task ID")
        return task_id

    async def _poll(self, task_id: str, max_wait: int = 120) -> Dict[str, Any]:
        """Poll ``res.php`` until the task is ready, returning the raw text result."""
        session = await self._get_session()
        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(5)
            elapsed += 5
            payload = {
                'key': self.api_key,
                'action': 'get',
                'id': task_id,
                'json': 0,
            }
            try:
                async with session.get(
                    f'{self.BASE_URL}/res.php',
                    params=payload,
                    headers={'Accept': 'text/plain'},
                ) as resp:
                    text = await resp.text()
            except Exception:
                continue

            body = str(text or '').strip()
            if body == 'CAPCHA_NOT_READY':
                continue
            if body.startswith('OK|'):
                return {'token': body[3:]}
            if body.startswith('ERROR_'):
                raise ValueError(f"2Captcha error: {body}")

        raise ValueError(f"Timeout while waiting for task {task_id}")

    async def create_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a task and return ``{'taskId': ...}`` (RetryMixin contract)."""
        task_id = await self._submit(params)
        return {'taskId': task_id}

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Poll for a task result and return ``{'solution': ...}`` (RetryMixin contract)."""
        solution = await self._poll(task_id)
        return {'solution': solution}

    async def solve_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a fully-specified 2Captcha task and return its solution.

        ``params`` are merged into the ``in.php`` query string verbatim, so new
        2Captcha ``method`` values work without changes here.
        """
        if not isinstance(params, dict) or not str(params.get('method') or '').strip():
            raise ValueError("2Captcha task must be a mapping with a non-empty 'method'")
        return await self._solve_with_retries(lambda: dict(params))

    async def hcaptcha(
        self,
        sitekey: str,
        website_url: str,
        proxy: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Solve hCaptcha through the native 2Captcha API.

        Args:
            sitekey: hCaptcha site key.
            website_url: Page URL the challenge belongs to.
            proxy: Optional proxy in 2Captcha ``user:pass@host:port`` form.
            options: Additional fields (``userAgent``, ``isInvisible``, ``rqdata``).
            rotate: Optional callable to rotate the browser/header profile
                before each retry.

        Returns:
            Solution dict containing ``gRecaptchaResponse``.
        """
        options = options or {}

        def build_params() -> Dict[str, Any]:
            params: Dict[str, Any] = {
                'method': 'hcaptcha',
                'sitekey': sitekey,
                'pageurl': website_url,
            }
            if proxy:
                params['proxy'] = proxy
            if options.get('userAgent'):
                params['userAgent'] = options['userAgent']
            if options.get('isInvisible'):
                params['invisible'] = 1
            if options.get('rqdata'):
                params['data'] = options['rqdata']
            return params

        result = await self._solve_with_retries(build_params, rotate=rotate)
        token = str(result.get('token') or result.get('gRecaptchaResponse') or '').strip()
        if not token:
            raise ValueError("2Captcha returned an empty hCaptcha solution")
        return {'gRecaptchaResponse': token}

    async def image_captcha(
        self,
        image_base64: str,
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Solve an image captcha via 2Captcha ``method=base64``.

        Args:
            image_base64: Base64 encoded image (raw base64 or data: URI).
            rotate: Optional callable to rotate the browser/header profile
                before each retry.

        Returns:
            Solution dict containing the recognized ``text``.
        """
        body = str(image_base64 or '').strip()
        if body.startswith('data:'):
            _, _, body = body.partition(',')
        if not body:
            raise ValueError("Image captcha requires base64 image data")

        result = await self._solve_with_retries(
            lambda: {
                'method': 'base64',
                'body': body,
            },
            rotate=rotate,
        )
        text = str(result.get('token') or result.get('text') or '').strip()
        if not text:
            raise ValueError("2Captcha returned an empty image captcha solution")
        return {'text': text}
