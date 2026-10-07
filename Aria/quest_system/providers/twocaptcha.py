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
import os
import tempfile
import time
import zipfile
from typing import Callable, Dict, Any, Optional, Tuple

import aiohttp

from .base import RetryMixin


def _selenium_verify_hcaptcha(
    page_url: str,
    token: str,
    proxy: Optional[str] = None,
    user_agent: Optional[str] = None,
    timeout: int = 45,
) -> Tuple[bool, str]:
    """Inject a solved hCaptcha token into the live widget with Selenium.

    Opens the challenge page in headless Chrome, waits for the hCaptcha
    widget, writes the token into every ``h-captcha-response`` and
    ``g-recaptcha-response`` field (inside the widget iframes and the top
    document), and pokes the common onVerify callbacks.

    Returns ``(accepted, detail)``. Never raises: any failure is reported as
    ``(False, reason)`` so the caller can fall back to the plain token.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
    except Exception as exc:
        return False, f"selenium unavailable: {exc}"

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--log-level=3")
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    temp_ext = None
    if proxy:
        from urllib.parse import urlsplit
        parts = urlsplit(str(proxy).strip())
        scheme = (parts.scheme or "http").lower()
        if scheme == "https":
            scheme = "http"
        host_port = f"{parts.hostname or ''}:{parts.port or ('' if parts.hostname else '')}".rstrip(":")
        if not parts.hostname:
            return False, "invalid proxy URL"
        if parts.username:
            # Chrome needs an extension for authenticated proxies.
            try:
                import base64 as _b64
                manifest = (
                    '{"version":"1.0.0","manifest_version":2,"name":"aria-proxy",'
                    '"permissions":["proxy","tabs","unlimitedStorage","storage",'
                    '"<all_urls>","webRequest","webRequestBlocking"],'
                    '"background":{"scripts":["background.js"]}}'
                )
                js = (
                    f'var config={{mode:"fixed_servers",rules:{{singleProxy:{{scheme:"{scheme}",'
                    f'host:"{parts.hostname}",port:parseInt({parts.port or 80})}},'
                    f'bypassList:[]}}}};chrome.proxy.settings.set({{value:config,scope:"regular"}},'
                    'function(){});function callbackFn(details){return{authCredentials:{username:"'
                    f'{parts.username}",password:"{parts.password or ""}"}}}}'
                    'chrome.webRequest.onAuthRequired.addListener("callbackFn",'
                    '{urls:["<all_urls>"]},["blocking"]);'
                )
                temp_ext = tempfile.mkdtemp(prefix="aria_proxy_ext_")
                with open(os.path.join(temp_ext, "manifest.json"), "w") as f:
                    f.write(manifest)
                with open(os.path.join(temp_ext, "background.js"), "w") as f:
                    f.write(js)
                with zipfile.ZipFile(os.path.join(temp_ext, "ext.zip"), "w") as zf:
                    zf.write(os.path.join(temp_ext, "manifest.json"), "manifest.json")
                    zf.write(os.path.join(temp_ext, "background.js"), "background.js")
                opts.add_argument(f"--load-extension={os.path.join(temp_ext, 'ext.zip')}")
            except Exception as exc:
                return False, f"proxy extension failed: {exc}"
        else:
            opts.add_argument(f"--proxy-server={scheme}://{parts.hostname}:{parts.port or 80}")

    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(timeout)
        driver.get(page_url)

        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements("css selector", 'iframe[src*="hcaptcha"]')
            or d.find_elements("css selector", '[data-hcaptcha-widget-id]')
        )

        # Write the token into every response textarea, both inside the
        # hCaptcha iframes and in the top-level document.
        for frame in driver.find_elements("css selector", 'iframe[src*="hcaptcha"]'):
            try:
                driver.switch_to.frame(frame)
                driver.execute_script(
                    "const t=document.getElementsByName('h-captcha-response');"
                    "const g=document.getElementsByName('g-recaptcha-response');"
                    "for (const el of [...t, ...g]) { el.value = arguments[0]; }",
                    token,
                )
                driver.switch_to.default_content()
            except Exception:
                driver.switch_to.default_content()

        driver.execute_script(
            "const set=(sel)=>{for (const el of document.querySelectorAll(sel))"
            "{el.value = arguments[0]; el.innerHTML = arguments[0];}};"
            "set('[name=h-captcha-response]'); set('[name=g-recaptcha-response]');",
            token,
        )

        # Poke the widget: hidden anchor click + onVerify callbacks, best effort.
        driver.execute_script(
            "try { const a=document.querySelector('iframe[data-hcaptcha-widget-id]');"
            "if (a) a.contentWindow.postMessage(JSON.stringify({source:'hcaptcha',"
            "label:'challenge-closed'}),'*'); } catch(e) {}"
            "try { if (window.hcaptcha && hcaptcha.execute) hcaptcha.execute(); } catch(e) {}"
        )
        time.sleep(1.5)

        accepted = driver.execute_script(
            "const el=document.querySelector('[name=h-captcha-response]') ||"
            "document.querySelector('[name=g-recaptcha-response]');"
            "return !!(el && el.value);"
        )
        return bool(accepted), "token injected into widget"
    except Exception as exc:
        return False, f"selenium verification failed: {exc}"
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if temp_ext:
            try:
                import shutil
                shutil.rmtree(temp_ext, ignore_errors=True)
            except Exception:
                pass



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

        # Optional Selenium step: load the live page, inject the token into the
        # widget and confirm it sticks. Enabled with ARIA_CAPTCHA_SELENIUM=1.
        if str(os.environ.get('ARIA_CAPTCHA_SELENIUM', '')).strip() == '1':
            accepted, detail = _selenium_verify_hcaptcha(
                website_url, token, proxy=proxy,
                user_agent=options.get('userAgent'),
            )
            print(f"[CAPTCHA] 2Captcha selenium verification: "
                  f"{'OK' if accepted else 'skipped/failed'} ({detail})")

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
