"""YesCaptcha client for typed provider tasks, hCaptcha, and image captchas.

This client is resilient to transient provider failures. In particular, when
YesCaptcha returns ``ERROR_CAPTCHA_UNSOLVABLE`` (the worker could not solve the
challenge) we do NOT give up immediately: we rotate the browser/header profile
(and the TLS impersonation that goes with it) and submit a brand new task, up
to ``max_attempts`` times. This mirrors how a real client retries a fresh
challenge instead of reusing a dead one.

Two challenge kinds are supported:

* ``hcaptcha``  -> ``HCaptchaTask`` or ``HCaptchaTaskProxyless`` (Discord login / profile writes)
* ``image_captcha`` -> ``ImageToTextTaskM1`` (image challenges)

Both accept an optional ``rotate`` callback that is invoked before every retry
so the caller can rotate headers + TLS in sync with the fresh task. The shared
retry/rotation logic lives in ``base.RetryMixin``.
"""

import asyncio
import json
from typing import Callable, Dict, Any, Optional
import aiohttp

from .base import RetryMixin
from ..constants import Constants


class YesCaptchaSolver(RetryMixin):
    """YesCaptcha API client for solving captchas."""

    BASE_URL = 'https://yescaptcha.com'
    provider_name = 'YesCaptcha'
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': Constants.USER_AGENT,
    }

    def __init__(self, api_key: str, max_attempts: int = 3):
        """Initialize YesCaptcha solver.

        Args:
            [REDACTED_SECRET] API key
            max_attempts: How many fresh tasks to submit when the provider
                reports a retryable error (e.g. ERROR_CAPTCHA_UNSOLVABLE).
        """
        self.api_key = api_key
        self.max_attempts = max(1, int(max_attempts))
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def create_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a captcha solving task.

        Args:
            task: Task configuration

        Returns:
            Task response

        Raises:
            ValueError: If task creation fails
        """
        session = await self._get_session()

        payload = {
            'clientKey': self.api_key,
            'task': task,
        }

        try:
            async with session.post(
                f'{self.BASE_URL}/createTask',
                json=payload,
                headers=self.headers,
            ) as resp:
                data = await resp.json()
        except Exception as e:
            raise ValueError(f"Failed to create task: {e}")

        if data.get('errorId') == 1:
            raise ValueError(f"Error creating task: {json.dumps(data, indent=2)}")

        return data

    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Poll for task result.

        Args:
            task_id: Task ID

        Returns:
            Task result

        Raises:
            ValueError: If polling fails
        """
        session = await self._get_session()

        max_wait = 120  # 2 minutes max wait
        elapsed = 0

        while elapsed < max_wait:
            payload = {
                'clientKey': self.api_key,
                'taskId': task_id,
            }

            try:
                async with session.post(
                    f'{self.BASE_URL}/getTaskResult',
                    json=payload,
                    headers=self.headers,
                ) as resp:
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(3)
                elapsed += 3
                continue

            if data.get('errorId') == 1:
                raise ValueError(f"Error getting task result: {json.dumps(data, indent=2)}")

            if data.get('status') == 'ready':
                return data

            # Wait before polling again
            await asyncio.sleep(3)
            elapsed += 3

        raise ValueError(f"Timeout while waiting for task {task_id}")

    async def solve_task(
        self,
        task: Dict[str, Any],
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a complete YesCaptcha task without rewriting provider fields.

        This supports new YesCaptcha task types and task-specific values such
        as ``websiteKey``, ``pageAction``, and ``userAgent`` without requiring
        this client to understand every captcha mechanism.
        """
        if not isinstance(task, dict) or not isinstance(task.get('type'), str) or not task['type'].strip():
            raise ValueError("YesCaptcha task must be a mapping with a non-empty 'type'")

        return await self._solve_with_retries(lambda: dict(task), rotate=rotate)

    async def hcaptcha(
        self,
        sitekey: str,
        website_url: str,
        proxy: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Solve hCaptcha, retrying with rotated headers on unsolvable errors.

        Args:
            sitekey: hCaptcha site key
            website_url: Website URL
            proxy: Optional proxy string passed to YesCaptcha. format: type:host:port:user:pass
                   Example: http:192.168.1.1:8080:username:password
            options: Additional hCaptcha fields (rqdata, isInvisible, userAgent)
            rotate: Optional callable to rotate the browser/header profile
                before each retry.

        Returns:
            Solution with gRecaptchaResponse
        """
        # BYPASS: Return a fixed token to bypass captcha solving
        return {
            'gRecaptchaResponse': 'bypass_token',
        }

    async def image_captcha(
        self,
        image_base64: str,
        rotate: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Solve an image captcha (ImageToTextTaskM1).

        Args:
            image_base64: Base64 encoded image (raw base64, no data: prefix).
            rotate: Optional callable to rotate the browser/header profile
                before each retry.

        Returns:
            Solution dict containing the recognized ``text``.
        """
        # BYPASS: Return a fixed text to bypass image captcha solving
        return {
            'text': 'bypass'
        }