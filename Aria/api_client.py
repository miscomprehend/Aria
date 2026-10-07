import contextlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
import random
import time
import re
import threading
from collections import deque
from typing import Callable, Dict, Any, Optional, List, Tuple
from urllib.parse import parse_qsl, quote, urlsplit

# Try curl_cffi, fallback to requests
try:
    from curl_cffi.requests import Session, Response
except ImportError:
    try:
        import requests
        Session = requests.Session
        Response = requests.Response
    except ImportError:
        raise ImportError("Either curl_cffi or requests must be installed")

from header_spoofer import HeaderSpoofer
from rate_limit import RateLimiter
from cache import DiscordCache
from discord_api_types import RelationshipType


class CachedAPIResponse:
    def __init__(self, payload: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


class _CaptchaTaskFailed(Exception):
    """A provider task died (bad key, no balance, unsolvable) — drop that
    task instead of polling it forever."""


class RoutedSession:
    """Route Discord hosts through the protected client and all others cleanly."""

    _EXTERNAL_ALLOWED_HEADERS = {
        "accept",
        "content-type",
        "if-modified-since",
        "if-none-match",
        "range",
    }

    def __init__(self, internal_request: Callable[..., Any], external_session: Any = None, spoofer: Any = None):
        self._internal_request = internal_request
        # The spoofer owns the transport and may tear it down + rebuild it
        # during header/TLS rotation. Always dereference the *current* session
        # at request time instead of caching a stale (possibly closed) one.
        self._spoofer = spoofer
        self._external_session = external_session
        self._external_lock = threading.RLock()
        session = self._resolve_session()
        session.trust_env = False
        session.headers.clear()

    def _resolve_session(self) -> Any:
        if self._spoofer is not None:
            session = getattr(self._spoofer, "session", None)
            if session is not None:
                return session
        if self._external_session is not None:
            return self._external_session
        return Session()

    @staticmethod
    def _parse_url(url: str):
        parsed = urlsplit(str(url or ""))
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Routed requests require an HTTPS URL without embedded credentials.")
        return parsed

    @staticmethod
    def _is_discord_host(hostname: str) -> bool:
        hostname = str(hostname or "").casefold().rstrip(".")
        return hostname == "discord.com" or hostname.endswith(".discord.com")

    def request(self, method: str, url: str, **kwargs):
        parsed = self._parse_url(url)
        method = str(method or "GET").upper()
        if self._is_discord_host(parsed.hostname):
            path = parsed.path or "/"
            api_prefix = "/api/v9"
            if path == api_prefix:
                endpoint = "/"
                base_url = f"{parsed.scheme}://{parsed.netloc}{api_prefix}"
            elif path.startswith(api_prefix + "/"):
                endpoint = path[len(api_prefix):]
                base_url = f"{parsed.scheme}://{parsed.netloc}{api_prefix}"
            else:
                endpoint = path
                base_url = f"{parsed.scheme}://{parsed.netloc}"

            params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            supplied_params = kwargs.pop("params", None)
            if supplied_params:
                params.update(dict(supplied_params))
            data = kwargs.pop("data", None)
            json_data = kwargs.pop("json", None)
            if json_data is not None and data is None:
                data = json_data
            headers = kwargs.pop("headers", None)
            if headers is not None:
                if not isinstance(headers, dict):
                    raise TypeError("Discord request headers must be a dictionary.")
                headers = {
                    str(name): value
                    for name, value in headers.items()
                    if str(name).casefold() in {"accept", "content-type"}
                }
            files = kwargs.pop("files", None)
            timeout = kwargs.pop("timeout", 30)
            kwargs.pop("verify", None)
            kwargs.pop("allow_redirects", None)
            for credential_arg in ("auth", "cookies", "cert"):
                if kwargs.pop(credential_arg, None) is not None:
                    raise ValueError(f"Pass Discord credentials through the internal API client, not {credential_arg}.")
            if kwargs:
                raise TypeError(f"Unsupported routed request options: {', '.join(sorted(kwargs))}")
            return self._internal_request(
                method,
                endpoint,
                data=data,
                params=params or None,
                headers=headers,
                files=files,
                timeout=timeout,
                _base_url=base_url,
            )

        headers = kwargs.pop("headers", {}) or {}
        if not isinstance(headers, dict):
            raise TypeError("External request headers must be a dictionary.")
        safe_headers = {
            str(name): value
            for name, value in headers.items()
            if str(name).casefold() in self._EXTERNAL_ALLOWED_HEADERS
        }
        for credential_arg in ("auth", "cookies", "cert"):
            if kwargs.pop(credential_arg, None) is not None:
                raise ValueError(f"External requests cannot include {credential_arg}.")
        kwargs.pop("verify", None)
        kwargs["timeout"] = kwargs.get("timeout", 15)
        with self._external_lock:
            session = self._resolve_session()
            cookies = getattr(session, "cookies", None)
            clear_cookies = getattr(cookies, "clear", None)
            if callable(clear_cookies):
                clear_cookies()
            try:
                response = session.request(
                    method,
                    parsed.geturl(),
                    headers=safe_headers,
                    verify=True,
                    allow_redirects=False,
                    **kwargs,
                )
            finally:
                if callable(clear_cookies):
                    clear_cookies()
        return response

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)


class DiscordAPIClient:
    def __init__(self, token: str):
        self.system_check = "ui_theme_customization_297588166653902849_scheme"
        self.token = token
        self.header_spoofer = HeaderSpoofer()
        self.header_spoofer.initialize_with_token(token)
        self.session = RoutedSession(self.request, spoofer=self.header_spoofer)
        self.rate_limiter = RateLimiter()
        self.cache = DiscordCache(token)
        self.user_id: Optional[str] = None
        self.user_data: Optional[Dict[str, Any]] = None
        self.auth_failed = False
        self.verification_blocked = False
        self.verification_endpoint: Optional[str] = None
        self._response_cache: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_log_times: Dict[str, float] = {}
        self.last_request_latency_ms: Optional[float] = None
        self._latency_samples = deque(maxlen=25)
        # Global message rate limiter: 30 messages per minute (more conservative)
        self.message_timestamps = deque(maxlen=60)
        self._self_throttle_until = 0.0
        # Global reaction rate limiter: 60 reactions per minute (more conservative)
        self.reaction_timestamps = deque(maxlen=60)
        # Circuit breaker for safety
        self.circuit_breaker_hits = 0
        self.last_circuit_reset = time.time()
        self.circuit_open = False
        # Health monitor reference (set by bot after initialization)
        self.health_monitor = None
        self._captcha_provider_name: Optional[str] = None

    @staticmethod
    def _is_quest_endpoint(endpoint: str) -> bool:
        return str(endpoint or "").startswith("/quests")

    def _quest_captcha_cooling_down(self, endpoint: str) -> bool:
        """True while quest write endpoints are paused after an unsolved captcha."""
        if not self._is_quest_endpoint(endpoint):
            return False
        return time.time() < getattr(self, "_quest_captcha_blocked_until", 0.0)

    _VERIFICATION_PAUSE_SECONDS = 300.0

    def _block_verification(self, endpoint: str) -> None:
        """Record an unsolved challenge as a time-limited write pause.

        A failed captcha must never take commands down permanently: the pause
        auto-expires after a few minutes so the bot keeps working. Quest
        endpoints get their own shorter cooldown so a quest captcha cannot
        block profile/guild writes either.
        """
        if self._is_quest_endpoint(endpoint):
            self._quest_captcha_blocked_until = time.time() + 300
            return
        self.verification_blocked = True
        self.verification_endpoint = endpoint
        self.verification_blocked_until = time.time() + self._VERIFICATION_PAUSE_SECONDS
        print(f"[AUTH-CHALLENGE] Writes paused for {int(self._VERIFICATION_PAUSE_SECONDS / 60)} min "
              f"after unsolved captcha on {endpoint}; commands resume automatically.")

    def _verification_paused(self) -> bool:
        """True while the post-captcha write pause is active (auto-expires)."""
        if not getattr(self, "verification_blocked", False):
            return False
        until = float(getattr(self, "verification_blocked_until", 0.0) or 0.0)
        if until and time.time() >= until:
            self.verification_blocked = False
            self.verification_endpoint = None
            print("[AUTH-CHALLENGE] Verification pause expired; commands active again.")
            return False
        return True

    def _extract_captcha_challenge(self, response_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if not isinstance(response_data, dict):
            return None

        nested = response_data.get("captcha")
        if isinstance(nested, dict):
            nested = nested
        else:
            nested = {}

        sitekey = str(response_data.get("captcha_sitekey") or nested.get("sitekey") or "").strip()
        if not sitekey:
            return None

        service = str(response_data.get("captcha_service") or nested.get("service") or "hcaptcha").strip().lower()
        challenge = {
            "service": service,
            "sitekey": sitekey,
            "rqdata": str(response_data.get("captcha_rqdata") or nested.get("rqdata") or "").strip(),
            "rqtoken": str(response_data.get("captcha_rqtoken") or nested.get("rqtoken") or "").strip(),
            "session_id": str(response_data.get("captcha_session_id") or nested.get("session_id") or "").strip(),
        }
        if response_data.get("captcha") is not None and isinstance(response_data.get("captcha"), dict):
            challenge["website_url"] = str(response_data["captcha"].get("website_url") or "").strip()
            challenge["page_url"] = str(response_data["captcha"].get("page_url") or "").strip()
        return challenge

    def _has_captcha_indicators(self, response_data: Dict[str, Any]) -> bool:
        if not isinstance(response_data, dict):
            return False
        nested = response_data.get("captcha")
        if isinstance(nested, dict):
            nested_fields = nested
        else:
            nested_fields = {}
        verification_fields = (
            "captcha_key",
            "captcha_sitekey",
            "captcha_service",
            "captcha_rqdata",
            "captcha_rqtoken",
            "captcha_required",
            "captcha",
        )
        return any(response_data.get(field) or nested_fields.get(field) for field in verification_fields)

    def _get_captcha_provider_candidates(self) -> List[Dict[str, str]]:
        providers: List[Dict[str, str]] = []
        configured_key = ""
        configured_provider = "nocaptchaai"
        configured_api_url = ""
        try:
            import config as aria_config
            with contextlib.redirect_stdout(io.StringIO()):
                settings = aria_config.Config()
            configured_key = str(settings.get("captcha_api_key") or "").strip()
            configured_provider = str(settings.get("captcha_provider") or "nocaptchaai").strip().lower()
            configured_api_url = str(settings.get("captcha_api_url") or "").strip().rstrip("/")
            configured_yes_key = str(settings.get("yes_captcha_api_key") or "").strip()
        except Exception:
            configured_yes_key = ""
        nocaptcha_key = str(os.environ.get("NOCAPTCHAAI_API_KEY") or "").strip()
        yescaptcha_key = str(os.environ.get("YES_CAPTCHA_API_KEY") or "").strip() or configured_yes_key
        if configured_provider == "twocaptcha" and configured_key:
            # Native 2Captcha unless a custom (non-2captcha.com) base URL is set,
            # in which case the YesCaptcha-compatible task protocol is used.
            normalized_api_url = configured_api_url.rstrip("/")
            if normalized_api_url and normalized_api_url != "https://2captcha.com":
                try:
                    parsed = urlsplit(normalized_api_url)
                    valid_api_url = (
                        parsed.scheme.lower() == "https"
                        and parsed.hostname
                        and parsed.username is None
                        and parsed.password is None
                        and not parsed.query
                        and not parsed.fragment
                    )
                except ValueError:
                    valid_api_url = False
                if valid_api_url:
                    providers.append({
                        "name": "2Captcha-compatible provider",
                        "base_url": normalized_api_url,
                        "client_key": configured_key,
                        "protocol": "yescaptcha",
                    })
                else:
                    print("[CAPTCHA] Configured compatible-provider API URL is invalid; it must be a credential-free HTTPS URL.")
            else:
                providers.append({
                    "name": "2Captcha",
                    "base_url": "https://2captcha.com",
                    "client_key": configured_key,
                    "protocol": "twocaptcha",
                })
        if configured_key:
            if configured_provider == "yescaptcha":
                yescaptcha_key = yescaptcha_key or configured_key
            elif configured_provider == "nocaptchaai":
                nocaptcha_key = nocaptcha_key or configured_key
        if nocaptcha_key:
            providers.append({
                "name": "NoCaptchaAI",
                "base_url": "https://api.nocaptchaai.com",
                "client_key": nocaptcha_key,
                "protocol": "yescaptcha",
            })
        if yescaptcha_key:
            providers.append({
                "name": "YesCaptcha",
                "base_url": "https://api.yescaptcha.com",
                "client_key": yescaptcha_key,
                "protocol": "yescaptcha",
            })
        return providers

    def _create_captcha_task(self, provider: Dict[str, str], challenge: Dict[str, str]) -> Optional[str]:
        website_url = str(challenge.get("website_url") or challenge.get("page_url") or "https://discord.com/channels/@me").strip()
        if not website_url.startswith("https://"):
            website_url = "https://discord.com/channels/@me"

        if provider.get("protocol") == "twocaptcha":
            return self._create_twocaptcha_task(provider, challenge, website_url)

        payload = {
            "clientKey": provider["client_key"],
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": website_url,
                "websiteKey": challenge["sitekey"],
                "userAgent": self.header_spoofer.profile.user_agent,
                "isInvisible": False,
            },
        }
        if challenge.get("rqdata"):
            payload["task"]["rqdata"] = challenge["rqdata"]

        # YesCaptcha-compatible providers that support the proxied task type
        # get the active proxy so solving happens over the same IP.
        try:
            proxy_manager = getattr(self.header_spoofer, "proxy_manager", None)
            proxy_str = proxy_manager.get_yescaptcha_proxy() if proxy_manager else ""
            if proxy_str and proxy_str.split(":")[0] in {"http", "socks4", "socks5"}:
                payload["task"]["type"] = "HCaptchaTask"
                payload["task"]["proxy"] = proxy_str
        except Exception:
            pass
        try:
            response = self.session.post(
                f'{provider["base_url"]}/createTask',
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=30,
            )
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} createTask request failed: {exc}')
            return None

        if not response or getattr(response, "status_code", 0) != 200:
            detail = str(getattr(response, "text", "") or "").strip()[:200]
            hint = " (API key rejected; check your captcha API key)" if "apikey" in detail.lower() else ""
            print(f'[CAPTCHA] {provider["name"]} createTask failed with HTTP {getattr(response, "status_code", "no response")}: {detail}{hint}')
            return None

        try:
            payload_data = response.json()
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} createTask invalid JSON response: {exc}')
            return None

        if payload_data.get("errorId"):
            print(f'[CAPTCHA] {provider["name"]} createTask error: {payload_data}')
            return None

        task_id = str(payload_data.get("taskId") or "").strip()
        if not task_id:
            print(f'[CAPTCHA] {provider["name"]} createTask missing taskId: {payload_data}')
            return None
        return task_id

    def _create_twocaptcha_task(self, provider: Dict[str, str], challenge: Dict[str, str], website_url: str) -> Optional[str]:
        """Submit a task to the native 2Captcha ``in.php`` endpoint.

        2Captcha uses flat form parameters and returns ``OK|<taskId>`` or an
        ``ERROR_*`` string, unlike the YesCaptcha JSON task envelope. When an
        active proxy is available from the proxy manager it is passed along so
        2Captcha solves the challenge through the same IP the session uses.
        """
        params = {
            "key": provider["client_key"],
            "method": "hcaptcha",
            "sitekey": challenge["sitekey"],
            "pageurl": website_url,
            "userAgent": self.header_spoofer.profile.user_agent,
            "json": 1,
            # Enterprise payload for Cloudflare-challenged pages such as
            # Discord: hands the worker the exact challenge context so it
            # doesn't burn 20-40s rediscovering it (or bounce the task).
            "enterprise": 1,
            "version": "enterprise",
            "sentry": True,
        }
        if challenge.get("rqdata"):
            params["data"] = challenge["rqdata"]

        try:
            proxy_manager = getattr(self.header_spoofer, "proxy_manager", None)
            if proxy_manager:
                proxy_str, proxytype = proxy_manager.get_2captcha_proxy()
                if proxy_str:
                    params["proxy"] = proxy_str
                    params["proxytype"] = proxytype
        except Exception as exc:
            print(f'[CAPTCHA] proxy lookup failed, continuing proxyless: {exc}')
        try:
            response = self.session.post(
                f'{provider["base_url"]}/in.php',
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/plain"},
                timeout=30,
            )
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} in.php request failed: {exc}')
            return None

        if not response or getattr(response, "status_code", 0) != 200:
            print(f'[CAPTCHA] {provider["name"]} in.php failed with HTTP {getattr(response, "status_code", "no response")}')
            return None

        body_text = str(getattr(response, "text", "") or "").strip()
        task_id = ""
        error_text = ""
        try:
            payload = response.json() if "application/json" in str(
                getattr(getattr(response, "headers", {}) or {}, "get", lambda *a, **k: "")("Content-Type", "")
            ) else json.loads(body_text)
            if isinstance(payload, dict):
                if payload.get("status") == 1:
                    task_id = str(payload.get("request") or "").strip()
                else:
                    error_text = str(payload.get("request") or body_text)
            else:
                error_text = body_text
        except Exception:
            # Plain-text fallback (json=0 style): OK|<id> or ERROR_*.
            if body_text.startswith("OK|"):
                task_id = body_text[3:].strip()
            else:
                error_text = body_text
        if task_id:
            return task_id
        if not error_text:
            print(f'[CAPTCHA] {provider["name"]} in.php returned an empty task ID')
            return None
        hint = " (check your 2Captcha API key or balance)" if "ERROR_" in error_text else ""
        print(f'[CAPTCHA] {provider["name"]} in.php error: {error_text[:200]}{hint}')
        return None

    @staticmethod
    def _jittered(base_seconds: float, fraction: float = 0.35) -> float:
        """Humanize a fixed wait: ±fraction randomness so poll/backoff timing
        never looks machine-regular. Result stays positive.

        Example: _jittered(5.0) -> 3.25 .. 6.75 seconds.
        """
        try:
            base = max(0.0, float(base_seconds))
        except (TypeError, ValueError):
            base = 0.0
        spread = base * max(0.0, min(fraction, 1.0))
        return max(0.25, base + random.uniform(-spread, spread))

    def _jittered_sleep(self, base_seconds: float, fraction: float = 0.35) -> float:
        """Sleep for a humanized duration; returns the actual seconds slept."""
        duration = self._jittered(base_seconds, fraction)
        if duration > 0:
            time.sleep(duration)
        return duration

    def _fetch_yescaptcha_status(self, provider: Dict[str, str], task_id: str) -> Optional[str]:
        """One getTaskResult check. Returns the token when ready, None while
        still solving or on transient errors. Raises _CaptchaTaskFailed when
        the provider reports the task as dead."""
        try:
            response = self.session.post(
                f'{provider["base_url"]}/getTaskResult',
                json={
                    "clientKey": provider["client_key"],
                    "taskId": task_id,
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=30,
            )
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} getTaskResult request failed: {exc}')
            return None

        if not response or getattr(response, "status_code", 0) != 200:
            print(f'[CAPTCHA] {provider["name"]} getTaskResult failed with HTTP {getattr(response, "status_code", "no response")}')
            return None

        try:
            payload_data = response.json()
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} getTaskResult invalid JSON response: {exc}')
            return None

        if payload_data.get("errorId"):
            raise _CaptchaTaskFailed(f'{provider["name"]} getTaskResult error: {payload_data}')

        status = str(payload_data.get("status") or "").strip().lower()
        if status == "ready":
            solution = payload_data.get("solution") or {}
            token = str(solution.get("gRecaptchaResponse") or solution.get("token") or "").strip()
            if token:
                return token
            raise _CaptchaTaskFailed(f'[CAPTCHA] {provider["name"]} returned ready status without token')
        return None

    def _poll_captcha_result(self, provider: Dict[str, str], task_id: str, timeout_seconds: float = 240.0) -> Optional[str]:
        if provider.get("protocol") == "twocaptcha":
            return self._poll_twocaptcha_result(provider, task_id, timeout_seconds)

        started = time.time()
        deadline = started + timeout_seconds
        next_progress = started + 30.0
        while time.time() < deadline:
            try:
                token = self._fetch_yescaptcha_status(provider, task_id)
            except _CaptchaTaskFailed as exc:
                print(f'[CAPTCHA] {exc}')
                return None
            if token:
                return token
            now = time.time()
            if now >= next_progress and now < deadline:
                print(f'[CAPTCHA] {provider["name"]} task {task_id} still solving ({now - started:.0f}s elapsed)...')
                next_progress = now + 30.0
            self._jittered_sleep(3)

        print(f'[CAPTCHA] {provider["name"]} timed out waiting for task {task_id}')
        return None

    def _fetch_twocaptcha_status(self, provider: Dict[str, str], task_id: str) -> Optional[str]:
        """One res.php check. Returns the token when ready, None while still
        solving or on transient errors. Raises _CaptchaTaskFailed when the
        provider reports the task as dead."""
        try:
            response = self.session.get(
                f'{provider["base_url"]}/res.php',
                params={
                    "key": provider["client_key"],
                    "action": "get",
                    "id": task_id,
                    "json": 1,
                },
                headers={"Accept": "application/json"},
                timeout=30,
            )
        except Exception as exc:
            print(f'[CAPTCHA] {provider["name"]} res.php request failed: {exc}')
            return None

        if not response or getattr(response, "status_code", 0) != 200:
            print(f'[CAPTCHA] {provider["name"]} res.php failed with HTTP {getattr(response, "status_code", "no response")}')
            return None

        payload: Any = None
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            status = payload.get("status")
            request_value = str(payload.get("request") or "").strip()
            if status == 1:
                if request_value:
                    return request_value
                raise _CaptchaTaskFailed(f'{provider["name"]} returned OK without a token')
            if request_value == "CAPCHA_NOT_READY":
                return None
            if request_value.startswith("ERROR_"):
                raise _CaptchaTaskFailed(f'{provider["name"]} res.php error: {request_value}')
            print(f'[CAPTCHA] {provider["name"]} res.php unexpected response: {request_value[:120]}')
            return None

        # Plain-text fallback for non-JSON replies.
        body = str(getattr(response, "text", "") or "").strip()
        if body == "CAPCHA_NOT_READY":
            return None
        if body.startswith("OK|"):
            token = body[3:].strip()
            if token:
                return token
            raise _CaptchaTaskFailed(f'{provider["name"]} returned OK without a token')
        if body.startswith("ERROR_"):
            raise _CaptchaTaskFailed(f'{provider["name"]} res.php error: {body}')
        print(f'[CAPTCHA] {provider["name"]} res.php unexpected response: {body[:120]}')
        return None

    def _poll_twocaptcha_result(self, provider: Dict[str, str], task_id: str, timeout_seconds: float = 240.0) -> Optional[str]:
        """Poll the native 2Captcha ``res.php`` endpoint for the solved token.

        The first check fires immediately (no sleep-then-check delay), then
        roughly every 5s with jitter. Progress is logged every 30s so long
        solves stay visible in the logs instead of going silent.
        """
        started = time.time()
        deadline = started + timeout_seconds
        next_progress = started + 30.0
        while time.time() < deadline:
            try:
                token = self._fetch_twocaptcha_status(provider, task_id)
            except _CaptchaTaskFailed as exc:
                print(f'[CAPTCHA] {exc}')
                return None
            if token:
                return token
            now = time.time()
            if now >= next_progress and now < deadline:
                print(f'[CAPTCHA] {provider["name"]} task {task_id} still solving ({now - started:.0f}s elapsed)...')
                next_progress = now + 30.0
            self._jittered_sleep(5)

        print(f'[CAPTCHA] {provider["name"]} timed out waiting for task {task_id}')
        return None

    def _rotate_captcha_transport(self, light: bool = False):
        """Rotate the browser profile and rebuild the TLS transport safely.

        Uses ``HeaderSpoofer.rebuild_session`` which validates the Chrome
        impersonation against the installed ``curl_cffi`` and falls back to a
        supported version. This avoids crashes such as
        "Impersonating chrome132 is not supported" that happened when the old
        code built ``CurlSession(impersonate=browser_target)`` directly from an
        arbitrary ``chrome<major>`` profile value.

        With ``light=True`` only the TLS session is rebuilt (no new profile,
        no build-number scrape) so challenge-retry round-trips stay fast.
        """
        try:
            if light:
                self.header_spoofer.rebuild_session()
            else:
                self.header_spoofer.rotate_profile()
                self.header_spoofer.rebuild_session()
        except Exception as exc:
            print(f"[CAPTCHA] TLS transport rotation failed: {exc}")

    def _solve_captcha_challenge(self, challenge: Dict[str, str], overall_timeout: float = 240.0) -> Optional[str]:
        """Solve using every configured provider at once; first token wins.

        Tasks are submitted to all providers in parallel, then polled
        round-robin — a slow or dead key no longer blocks the working ones
        behind a full sequential timeout. Progress is logged every 30s so
        the logs never go silent during a long solve.
        """
        if challenge.get("service") not in {"hcaptcha", ""}:
            print(f'[CAPTCHA] Unsupported captcha service: {challenge.get("service")}')
            return None

        providers = self._get_captcha_provider_candidates()
        if not providers:
            print('[CAPTCHA] No captcha API key configured. Set NOCAPTCHAAI_API_KEY (or YES_CAPTCHA_API_KEY), or captcha_api_key in the Aria config.')
            return None

        # Reuse a still-fresh token from an earlier challenge instead of
        # paying for a brand-new solve every time (hCaptcha tokens stay valid
        # ~2 minutes; reuse window kept to 90s).
        try:
            cached_token = str(getattr(self, "_last_captcha_token", "") or "").strip()
            cached_at = float(getattr(self, "_last_captcha_token_at", 0.0) or 0.0)
            if cached_token and (time.time() - cached_at) < 90.0:
                provider = providers[0]
                self._captcha_provider_name = f'{provider["name"]} (cached token)'
                print(f'[CAPTCHA] Reusing token solved {time.time() - cached_at:.0f}s ago; skipping new solve.')
                return cached_token
        except Exception:
            pass

        self._rotate_captcha_transport(light=True)

        def _submit_one(provider: Dict[str, str]) -> Tuple[Dict[str, str], Optional[str]]:
            try:
                return provider, self._create_captcha_task(provider, challenge)
            except Exception as exc:
                print(f'[CAPTCHA] {provider.get("name", "provider")} task submission crashed: {exc}')
                return provider, None

        if len(providers) == 1:
            submitted = [_submit_one(providers[0])]
        else:
            print(f'[CAPTCHA] Submitting captcha task to {len(providers)} providers in parallel...')
            with ThreadPoolExecutor(max_workers=len(providers)) as pool:
                submitted = list(pool.map(_submit_one, providers))

        pending: List[Tuple[Dict[str, str], str]] = []
        for provider, task_id in submitted:
            if task_id:
                print(f'[CAPTCHA] {provider["name"]} task {task_id} submitted; polling for solution...')
                pending.append((provider, task_id))
        if not pending:
            print('[CAPTCHA] No provider accepted the captcha task.')
            return None

        started = time.time()
        deadline = started + max(30.0, float(overall_timeout or 0))
        next_progress = started + 30.0
        while pending and time.time() < deadline:
            for provider, task_id in list(pending):
                try:
                    if provider.get("protocol") == "twocaptcha":
                        token = self._fetch_twocaptcha_status(provider, task_id)
                    else:
                        token = self._fetch_yescaptcha_status(provider, task_id)
                except _CaptchaTaskFailed as exc:
                    print(f'[CAPTCHA] {exc}; dropping {provider["name"]} task {task_id}.')
                    pending = [(p, t) for p, t in pending
                               if not (p.get("name") == provider.get("name") and t == task_id)]
                    continue
                except Exception as exc:
                    print(f'[CAPTCHA] {provider["name"]} poll crashed: {exc}')
                    continue
                if token:
                    self._captcha_provider_name = provider["name"]
                    print(f'[CAPTCHA] {provider["name"]} solved task {task_id} in {time.time() - started:.0f}s.')
                    try:
                        self._last_captcha_token = token
                        self._last_captcha_token_at = time.time()
                    except Exception:
                        pass
                    return token
            now = time.time()
            if pending and now >= next_progress and now < deadline:
                waiting = ", ".join(f'{p["name"]}({t})' for p, t in pending)
                print(f'[CAPTCHA] still waiting ({now - started:.0f}s elapsed) on: {waiting}')
                next_progress = now + 30.0
            if pending and time.time() < deadline:
                self._jittered_sleep(3)

        names = ", ".join(p["name"] for p in providers)
        print(f'[CAPTCHA] No solution from [{names}] after {overall_timeout:.0f}s.')
        self._rotate_captcha_transport()
        return None

    def _check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should open due to excessive rate limiting."""
        current_time = time.time()

        # Reset circuit breaker counters every 5 minutes
        if current_time - self.last_circuit_reset > 300:
            self.circuit_breaker_hits = 0
            self.last_circuit_reset = current_time
            self.circuit_open = False

        # Open circuit if too many rate limit hits in window
        if self.circuit_breaker_hits >= 10:
            if not self.circuit_open:
                self.circuit_open = True
                print("[CIRCUIT-BREAKER] Opening circuit - too many rate limits. Bot will be throttled for 5 minutes.")
            return True
        return False

    def _record_rate_limit_hit(self):
        """Record a rate limit hit for circuit breaker."""
        self.circuit_breaker_hits += 1

    def _self_throttle_wait(self, now: float) -> float:
        """Pause after a short burst so command spam does not trip automod.

        Eight sends inside ten seconds starts a thirty-second cooldown. A
        cooldown already in progress returns the time still remaining.
        """
        if now < self._self_throttle_until:
            return self._self_throttle_until - now
        recent = [stamp for stamp in self.message_timestamps if now - stamp <= 10.0]
        if len(recent) >= 8:
            self._self_throttle_until = now + 30.0
            return 30.0
        return 0.0

    def _get_exponential_backoff_wait(self, timestamps: deque, limit: int, base_wait: float = 1.0) -> Optional[float]:
        """Calculate exponential backoff wait time."""
        current_time = time.time()

        # Remove old timestamps
        while timestamps and current_time - timestamps[0] > 60:
            timestamps.popleft()

        if len(timestamps) >= limit:
            # Exponential backoff: wait longer if we're consistently hitting limits
            excess = len(timestamps) - limit + 1
            wait_time = base_wait * (2 ** min(excess, 5))  # Cap at 32x base wait
            return min(wait_time, 60.0)  # Max 1 minute wait
        return None

    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        self.circuit_breaker_hits = 0
        self.last_circuit_reset = time.time()
        self.circuit_open = False
        print("[CIRCUIT-BREAKER] Manually reset")

    def get_safety_status(self) -> Dict[str, Any]:
        """Get current safety status for monitoring."""
        current_time = time.time()
        return {
            "circuit_breaker_open": self.circuit_open,
            "circuit_breaker_hits": self.circuit_breaker_hits,
            "verification_blocked": self.verification_blocked,
            "messages_last_minute": len([t for t in self.message_timestamps if current_time - t <= 60]),
            "self_throttle_remaining": max(0.0, self._self_throttle_until - current_time),
            "reactions_last_minute": len([t for t in self.reaction_timestamps if current_time - t <= 60]),
            "time_since_circuit_reset": current_time - self.last_circuit_reset
        }

    def _is_cacheable_get(self, method: str, endpoint: str) -> bool:
        if method != "GET":
            return False
        normalized = endpoint.split("?", 1)[0]
        return normalized in {
            "/users/@me/guilds",
            "/users/@me/channels",
            "/users/@me/relationships",
        }

    def _response_cache_ttl(self, endpoint: str) -> float:
        normalized = endpoint.split("?", 1)[0]
        if "with_counts=true" in endpoint:
            return 45.0
        if normalized == "/users/@me/channels":
            return 30.0
        if normalized == "/users/@me/relationships":
            return 30.0
        return 180.0

    def _is_auth_sensitive_403(self, endpoint: str) -> bool:
        normalized = endpoint.split("?", 1)[0]
        if normalized in {
            "/users/@me",
            "/users/@me/settings",
            "/users/@me/channels",
            "/users/@me/relationships",
            "/users/@me/guilds",
            "/users/@me/library",
        }:
            return True
        return bool(re.match(r"^/guilds/\d+/members/@me$", normalized))

    def _get_cached_response(self, endpoint: str, allow_stale: bool = False) -> Optional[CachedAPIResponse]:
        entry = self._response_cache.get(endpoint)
        if not entry:
            return None
        age = time.time() - float(entry.get("timestamp", 0.0) or 0.0)
        ttl = float(entry.get("ttl", self._response_cache_ttl(endpoint)))
        if not allow_stale and age > ttl:
            return None
        return CachedAPIResponse(entry.get("payload"), status_code=200, headers=entry.get("headers") or {})

    def _store_cached_response(self, endpoint: str, response: Any):
        try:
            payload = response.json()
        except Exception:
            return
        self._response_cache[endpoint] = {
            "payload": payload,
            "headers": dict(getattr(response, "headers", {}) or {}),
            "timestamp": time.time(),
            "ttl": self._response_cache_ttl(endpoint),
        }

    def _overwrite_cached_response(self, endpoint: str, payload: Any):
        self._response_cache[endpoint] = {
            "payload": payload,
            "headers": {},
            "timestamp": time.time(),
            "ttl": self._response_cache_ttl(endpoint),
        }

    def _upsert_cached_dm_channel(self, dm_channel: Dict[str, Any]):
        endpoint = "/users/@me/channels"
        cached = self._get_cached_response(endpoint, allow_stale=True)
        channels = list(cached.json() or []) if cached is not None else []
        channel_id = str(dm_channel.get("id") or "")
        if not channel_id:
            return
        updated = False
        for index, channel in enumerate(channels):
            if str(channel.get("id") or "") == channel_id:
                channels[index] = dm_channel
                updated = True
                break
        if not updated:
            channels.append(dm_channel)
        self._overwrite_cached_response(endpoint, channels)

    def _record_latency(self, started_at: float):
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        self.last_request_latency_ms = latency_ms
        self._latency_samples.append(latency_ms)

    def get_latency_metrics(self) -> Dict[str, Optional[float]]:
        samples = list(self._latency_samples)
        if not samples:
            return {"last_ms": self.last_request_latency_ms, "avg_ms": None, "best_ms": None, "samples": 0}
        return {
            "last_ms": self.last_request_latency_ms,
            "avg_ms": (sum(samples) / len(samples)),
            "best_ms": min(samples),
            "samples": len(samples),
        }

    def request_external(self, method: str, url: str, **kwargs):
        """Send an unauthenticated HTTPS request outside Discord's API host."""
        parsed = urlsplit(str(url or ""))
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("External requests require a public HTTPS URL without embedded credentials.")

        headers = kwargs.pop("headers", {}) or {}
        if not isinstance(headers, dict):
            raise TypeError("External request headers must be a dictionary.")
        allowed_headers = {
            "accept",
            "content-type",
            "if-modified-since",
            "if-none-match",
            "range",
        }
        safe_headers = {}
        for name, value in headers.items():
            normalized = str(name).casefold()
            if normalized in allowed_headers:
                safe_headers[str(name)] = value

        kwargs.setdefault("timeout", 15)
        return self.session.request(str(method).upper(), parsed.geturl(), headers=safe_headers, **kwargs)

    def _validate_system(self):
        check_parts = self.system_check.split("_")
        if len(check_parts) != 5:
            return False
        if "297588166653902849" not in self.system_check:
            return False
        return True

    def request(self, method: str, endpoint: str, data: Optional[Any] = None,
                params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                max_retries: int = 3, retry_count: int = 0,
                json: Optional[Any] = None, files: Optional[Any] = None,
                timeout: float = 30, _base_url: str = "https://discord.com/api/v9",
                _global_retry: int = 0, _transport_retry: int = 0,
                _header_rotations: int = 0) -> Optional[Any]:
        if json is not None and data is None:
            data = json
        """
        Enhanced request handler with comprehensive captcha support for all Discord API operations.
        Handles: join invites, profile updates, message operations, quest enrollment, etc.
        """
        # Global recursion guard: hard limit to prevent infinite recursion
        if _global_retry > 10:
            print(f"[REQUEST-ERROR] {method} {endpoint}: exceeded global retry limit, aborting.")
            return None
        # A pending verification only blocks writes; GETs (quest listing,
        # guilds, channels) must keep working so the UI doesn't go dark.
        # The write pause is time-limited and expires automatically.
        if method != "GET" and (self.auth_failed or self._verification_paused()):
            return None
        if method != "GET" and self._quest_captcha_cooling_down(endpoint):
            return None

        if self._is_cacheable_get(method, endpoint):
            cached = self._get_cached_response(endpoint)
            if cached is not None:
                return cached

        wait_time = self.rate_limiter.get_wait_time(endpoint)
        if wait_time:
            # Humanize bucket waits slightly so a burst of retries never
            # lands on a perfectly regular cadence.
            time.sleep(self._jittered(wait_time, 0.15))

        url = f"{_base_url}{endpoint}"
        request_headers = self.header_spoofer.get_protected_headers(self.token)
        if data is not None and files is None and method in {"POST", "PATCH", "PUT"}:
            request_headers.setdefault("Content-Type", "application/json")
        if headers:
            request_headers.update(headers)

        request_started_at = time.perf_counter()

        try:
            if method == "GET":
                response = self.header_spoofer.session.get(url, headers=request_headers, params=params, verify=False, timeout=timeout)
            elif method == "POST":
                if files is not None:
                    response = self.header_spoofer.session.post(url, headers=request_headers, data=data, files=files, verify=False, timeout=timeout)
                else:
                    response = self.header_spoofer.session.post(url, headers=request_headers, json=data, verify=False, timeout=timeout)
            elif method == "DELETE":
                response = self.header_spoofer.session.delete(url, headers=request_headers, verify=False, timeout=timeout)
            elif method == "PATCH":
                response = self.header_spoofer.session.patch(url, headers=request_headers, json=data, verify=False, timeout=timeout)
            elif method == "PUT":
                response = self.header_spoofer.session.put(url, headers=request_headers, json=data, verify=False, timeout=timeout)
            else:
                return None

            self._record_latency(request_started_at)

            # Handle 401 - token is invalid, no point retrying
            if response.status_code == 401:
                if not self.auth_failed:
                    print(f"[AUTH-ERROR] 401 on {endpoint} - token is invalid or expired. Halting requests.")
                    self.auth_failed = True
                    # Record auth error with health monitor
                    if self.health_monitor:
                        self.health_monitor.record_auth_error({
                            'status_code': 401,
                            'endpoint': endpoint,
                            'message': 'Token is invalid or expired'
                        })
                return response

            response_data = {}
            if response.status_code in {400, 403, 429}:
                try:
                    response_data = response.json()
                    if not isinstance(response_data, dict):
                        response_data = {}
                except Exception:
                    response_data = {}

            if response.status_code in {400, 403}:
                try:
                    challenge = self._extract_captcha_challenge(response_data)
                    if challenge:
                        # Single bypass rotation: Discord often flags a stale
                        # fingerprint rather than truly requiring a captcha, so
                        # retry once locally with fresh headers before paying a
                        # solver. Exactly one retry keeps the token's request
                        # count to: original + 1 bypass + 1 solved = 3 max.
                        if _header_rotations < 1 and not challenge.get("rqtoken"):
                            try:
                                self.header_spoofer.rotate_profile()
                            except Exception as rot_exc:
                                print(f"[CAPTCHA] header rotation failed: {rot_exc}")
                            print(f"[CAPTCHA] {endpoint} challenged; rotated headers and retrying once before solving.")
                            return self.request(
                                method,
                                endpoint,
                                data=data,
                                params=params,
                                headers=headers,
                                max_retries=max_retries,
                                retry_count=retry_count,
                                json=json,
                                files=files,
                                timeout=timeout,
                                _base_url=_base_url,
                                _global_retry=_global_retry + 1,
                                _transport_retry=_transport_retry,
                                _header_rotations=_header_rotations + 1,
                            )

                        # (The solve itself rotates the transport via
                        # _solve_captcha_challenge, so the solved token goes
                        # out on a fingerprint that never saw the challenge.)

                        if retry_count < max_retries:
                            solved_token = self._solve_captcha_challenge(challenge)
                            if solved_token:
                                captcha_headers = dict(headers or {})
                                captcha_headers["X-Captcha-Key"] = solved_token
                                if challenge.get("rqtoken"):
                                    captcha_headers["X-Captcha-Rqtoken"] = challenge["rqtoken"]
                                if challenge.get("session_id"):
                                    captcha_headers["X-Captcha-Session-Id"] = challenge["session_id"]

                                provider_name = self._captcha_provider_name or "captcha provider"
                                print(f"[CAPTCHA] Solved with {provider_name}; retrying {endpoint} ({retry_count + 1}/{max_retries})")
                                solved_response = self.request(
                                    method,
                                    endpoint,
                                    data=data,
                                    params=params,
                                    headers=captcha_headers,
                                    max_retries=max_retries,
                                    retry_count=retry_count + 1,
                                    json=json,
                                    files=files,
                                    timeout=timeout,
                                    _base_url=_base_url,
                                    _global_retry=_global_retry + 1,
                                    _transport_retry=_transport_retry,
                                    _header_rotations=_header_rotations,
                                )
                                # Token rejected again (stale/expired solve):
                                # rotate once and let the outer solve run afresh
                                # rather than hammering the endpoint.
                                if (solved_response is not None
                                        and getattr(solved_response, "status_code", None) in {400, 403}):
                                    try:
                                        self.header_spoofer.rotate_profile()
                                    except Exception:
                                        pass
                                return solved_response

                        self._block_verification(endpoint)
                        print(f"[AUTH-CHALLENGE] Discord requires verification for {endpoint}; captcha solve failed or unavailable.")
                        return response
                    if self._has_captcha_indicators(response_data):
                        self._block_verification(endpoint)
                        print(f"[AUTH-CHALLENGE] Discord requires verification for {endpoint}; challenge is missing sitekey.")
                        return response

                    if response.status_code == 400:
                        error_code = response_data.get("code", 0)
                        error_msg = response_data.get("message", str(response_data))
                        print(f"[API-ERROR] {endpoint}: [{error_code}] {error_msg}")
                except Exception:
                    pass

            # Store the complete cooldown and return the failed request without replaying it.
            if response.status_code == 429:
                self._record_rate_limit_hit()  # Record for circuit breaker
                # Record rate limit error with health monitor
                if self.health_monitor:
                    self.health_monitor.record_rate_limit_error()
                retry_after = self.rate_limiter.handle_429(
                    dict(response.headers),
                    endpoint,
                    global_rate_limit=bool(response_data.get("global")),
                    retry_after=response_data.get("retry_after"),
                )
                if self._is_cacheable_get(method, endpoint):
                    cached = self._get_cached_response(endpoint, allow_stale=True)
                    if cached is not None:
                        last_logged_at = self._rate_limit_log_times.get(endpoint, 0.0)
                        now = time.time()
                        if now - last_logged_at >= 30.0:
                            print(f"[RATE-LIMIT] Using cached response for {endpoint}; cooldown {retry_after}s")
                            self._rate_limit_log_times[endpoint] = now
                        return cached
                last_logged_at = self._rate_limit_log_times.get(endpoint, 0.0)
                now = time.time()
                if now - last_logged_at >= 30.0:
                    print(f"[RATE-LIMIT] {endpoint} blocked for {retry_after}s; request was not retried.")
                    self._rate_limit_log_times[endpoint] = now
                return response

            # Update rate limit buckets
            if "X-RateLimit-Bucket" in response.headers:
                bucket_hash = self.rate_limiter.parse_bucket_hash(dict(response.headers))
                self.rate_limiter.record_endpoint_bucket(endpoint, bucket_hash)
                self.rate_limiter.update_bucket(bucket_hash, dict(response.headers))

            if response.status_code == 200 and self._is_cacheable_get(method, endpoint):
                self._store_cached_response(endpoint, response)

            self.rate_limiter.decrement(endpoint)
            return response

        except Exception as e:
            msg = str(e)
            tls_version_error = "wrong_version_number" in msg.casefold() or "wrong version number" in msg.casefold()
            if tls_version_error and _transport_retry < 1:
                try:
                    self.header_spoofer.rebuild_session()
                except Exception as rebuild_error:
                    print(f"[REQUEST-ERROR] {method} {endpoint}: TLS session recovery failed: {rebuild_error}")
                    return None
                print(f"[NETWORK] TLS handshake failed for {endpoint}; rebuilt session and retrying once.")
                return self.request(
                    method,
                    endpoint,
                    data=data,
                    params=params,
                    headers=headers,
                    max_retries=max_retries,
                    retry_count=retry_count,
                    json=json,
                    files=files,
                    timeout=timeout,
                    _base_url=_base_url,
                    _global_retry=_global_retry,
                    _transport_retry=_transport_retry + 1,
                )
            if "curl: (23)" in msg or "Failure writing output" in msg or "SSLError" in msg:
                return None
            print(f"[REQUEST-ERROR] {method} {endpoint}: {e}")
            return None

    def request_as_token(self, method: str, endpoint: str, token: str, **kwargs):
        """Make a Discord API request using a separately supplied raw token."""
        token = str(token or "").strip()
        if not token:
            raise ValueError("A token is required for this Discord API request.")
        request_headers = self.header_spoofer.get_protected_headers(token)
        return self.request(method, endpoint, headers=request_headers, **kwargs)

    def get_user_info(self, force: bool = False) -> Optional[Dict[str, Any]]:
        if not force:
            cached = self.cache.get_user()
            if cached:
                self.user_data = cached
                self.user_id = cached.get("id")
                return cached

        response = self.request("GET", "/users/@me")
        if response is None:
            print("[USER-INFO] Failed to fetch /users/@me, aborting to prevent recursion.")
            return None
        if hasattr(response, "status_code") and response.status_code == 200:
            data = response.json()
            self.user_data = data
            self.user_id = data.get("id")
            self.cache.save_user(data)
            return data
        print(f"[USER-INFO] /users/@me failed with status: {getattr(response, 'status_code', 'no response')}")
        return None

    def edit_profile(self, **fields) -> Optional[Any]:
        """Update account-level profile fields through the protected request path."""
        if not fields:
            raise ValueError("At least one profile field is required.")
        return self.request("PATCH", "/users/@me", data=fields)

    def edit_profile_details(self, **fields) -> Optional[Any]:
        """Update bio/pronouns through the protected profile request path."""
        if not fields:
            raise ValueError("At least one profile detail is required.")
        return self.request("PATCH", "/users/@me/profile", data=fields)

    def _normalize_outbound_text(self, content: str) -> str:
        """Preserve intentional Discord formatting while normalizing null content."""
        return "" if content is None else str(content)

    def send_message(self, channel_id: str, content: str, reply_to: Optional[str] = None,
                    tts: bool = False) -> Optional[Dict[str, Any]]:
        # Check circuit breaker first
        if self._check_circuit_breaker():
            print("[CIRCUIT-BREAKER] Message blocked - circuit is open")
            return None

        # Burst pause: 8 messages inside 10s is enough to trip Discord automod
        # even when the per-minute cap has not been reached yet.
        current_time = time.time()
        burst_wait = self._self_throttle_wait(current_time)
        if burst_wait:
            print(f"[SELF-THROTTLE] Pausing outbound messages for {burst_wait:.1f}s")
            time.sleep(burst_wait)
            current_time = time.time()

        # Global message rate limiting: max 30 messages per minute with exponential backoff
        wait_time = self._get_exponential_backoff_wait(self.message_timestamps, 30, 1.0)
        if wait_time:
            print(f"[GLOBAL-RATE-LIMIT] Message rate limit reached, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self._record_rate_limit_hit()

        self.message_timestamps.append(current_time)

        # Discord content safety: ensure valid UTF-8 text and <= 2000 chars per message.
        # This prevents 50035 Invalid Form Body for oversized/invalid payloads.
        try:
            safe_content = self._normalize_outbound_text(content)
        except Exception:
            safe_content = ""
        safe_content = safe_content.encode("utf-8", "ignore").decode("utf-8", "ignore")
        if not safe_content.strip():
            safe_content = "."

        chunks: List[str] = []
        if len(safe_content) <= 2000:
            chunks = [safe_content]
        else:
            start = 0
            n = len(safe_content)
            while start < n:
                end = min(start + 2000, n)
                piece = safe_content[start:end]
                if end < n:
                    nl = piece.rfind("\n")
                    if nl >= 1200:
                        piece = piece[:nl]
                        end = start + nl
                piece = piece.rstrip("\n")
                if not piece:
                    piece = safe_content[start:min(start + 2000, n)]
                    end = start + len(piece)
                chunks.append(piece)
                start = end

        last_message = None
        for i, chunk in enumerate(chunks):
            data = {"content": chunk, "tts": tts}
            # Only apply message reference to the first chunk.
            if reply_to and i == 0:
                data["message_reference"] = {"message_id": reply_to}

            response = self.request("POST", f"/channels/{channel_id}/messages", data=data)
            if response and response.status_code == 200:
                last_message = response.json()
            else:
                # Stop on first failed chunk so we don't spam partial output.
                break

        return last_message

    def delete_message(self, channel_id: str, message_id: str) -> bool:
        response = self.request("DELETE", f"/channels/{channel_id}/messages/{message_id}")
        return response.status_code == 204 if response else False

    def edit_message(self, channel_id: str, message_id: str, content: str) -> Optional[Dict[str, Any]]:
        try:
            safe_content = self._normalize_outbound_text(content)
        except Exception:
            safe_content = ""
        safe_content = safe_content.encode("utf-8", "ignore").decode("utf-8", "ignore")
        if not safe_content.strip():
            safe_content = "."
        if len(safe_content) > 2000:
            safe_content = safe_content[:2000]
        data = {"content": safe_content}
        response = self.request("PATCH", f"/channels/{channel_id}/messages/{message_id}", data=data)
        return response.json() if response and response.status_code == 200 else None

    def get_messages(self, channel_id: str, limit: int = 50, before: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before

        response = self.request("GET", f"/channels/{channel_id}/messages", params=params)
        if response and response.status_code == 200:
            messages = response.json()
            for msg in messages:
                self.cache.cache_message(msg)
            return messages
        return []

    def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> bool:
        # Check circuit breaker first
        if self._check_circuit_breaker():
            print("[CIRCUIT-BREAKER] Reaction blocked - circuit is open")
            return False

        # Global reaction rate limiting: max 60 reactions per minute with exponential backoff
        current_time = time.time()
        wait_time = self._get_exponential_backoff_wait(self.reaction_timestamps, 60, 0.5)
        if wait_time:
            print(f"[GLOBAL-RATE-LIMIT] Reaction rate limit reached, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            self._record_rate_limit_hit()

        self.reaction_timestamps.append(current_time)

        encoded_emoji = quote(emoji)
        response = self.request(
            "PUT",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me",
            headers={"referer": f"https://discord.com/channels/@me/{channel_id}"},
        )
        return response.status_code == 204 if response else False

    def redeem_gift_code(self, code: str) -> Optional[Any]:
        code = str(code or "").strip()
        if not code:
            return None
        return self.request(
            "POST",
            f"/entitlements/gift-codes/{code}/redeem",
            data={},
            headers={"referer": "https://discord.com/store"},
        )

    def create_dm(self, user_id: str) -> Optional[Dict[str, Any]]:
        for channel in self.get_dm_channels(force=False):
            recipients = channel.get("recipients") or []
            for recipient in recipients:
                if str(recipient.get("id") or "") == str(user_id):
                    return channel
        data = {"recipient_id": user_id}
        response = self.request("POST", "/users/@me/channels", data=data)
        if response and response.status_code == 200:
            dm_channel = response.json()
            if isinstance(dm_channel, dict):
                self._upsert_cached_dm_channel(dm_channel)
            return dm_channel
        return None

    def join_guild(self, invite_code: str) -> Optional[Dict[str, Any]]:
        response = self.request("POST", f"/invites/{invite_code}")
        return response.json() if response and response.status_code == 200 else None

    def leave_guild(self, guild_id: str) -> bool:
        response = self.request("DELETE", f"/users/@me/guilds/{guild_id}")
        return response.status_code == 204 if response else False

    def trigger_typing(self, channel_id: str) -> bool:
        response = self.request("POST", f"/channels/{channel_id}/typing")
        return response.status_code == 204 if response else False

    def set_status(self, status: str, activities: Optional[List[Dict]] = None) -> bool:
        data = {
            "status": status,
            "activities": activities or [],
            "since": int(time.time() * 1000)
        }
        response = self.request("POST", "/users/@me/settings", data=data)
        return response.status_code == 200 if response else False

    def get_guilds(self, force: bool = False) -> List[Dict[str, Any]]:
        if not force:
            cached = self.cache.get_guilds()
            if cached:
                return cached

        response = self.request("GET", "/users/@me/guilds")
        if response and response.status_code == 200:
            guilds = response.json()
            self.cache.save_guilds(guilds)
            return guilds
        return []

    def acknowledge_all_guilds(self) -> Dict[str, Any]:
        """Mark every guild text channel with a latest message as read."""
        result: Dict[str, Any] = {
            "guilds": 0,
            "channels": 0,
            "acked": 0,
            "guilds_failed": 0,
            "channels_failed": 0,
            "error": "",
        }

        guild_response = self.request("GET", "/users/@me/guilds")
        if guild_response is None or getattr(guild_response, "status_code", None) != 200:
            status = getattr(guild_response, "status_code", "no response")
            result["error"] = f"Could not fetch guild list (HTTP {status})."
            return result

        try:
            guilds = guild_response.json()
        except (TypeError, ValueError):
            result["error"] = "Discord returned an invalid guild list."
            return result
        if not isinstance(guilds, list):
            result["error"] = "Discord returned an invalid guild list."
            return result

        result["guilds"] = len(guilds)
        readable_channel_types = {0, 5, 10, 11, 12, 15, 16}
        for guild in guilds:
            if not isinstance(guild, dict) or not guild.get("id"):
                result["guilds_failed"] += 1
                continue

            channels_response = self.request("GET", f"/guilds/{guild['id']}/channels")
            if channels_response is None or getattr(channels_response, "status_code", None) != 200:
                result["guilds_failed"] += 1
                continue

            try:
                channels = channels_response.json()
            except (TypeError, ValueError):
                result["guilds_failed"] += 1
                continue
            if not isinstance(channels, list):
                result["guilds_failed"] += 1
                continue

            for channel in channels:
                if not isinstance(channel, dict):
                    continue
                try:
                    channel_type = int(channel.get("type", -1))
                except (TypeError, ValueError):
                    continue
                channel_id = channel.get("id")
                last_message_id = channel.get("last_message_id")
                if channel_type not in readable_channel_types or not channel_id or not last_message_id:
                    continue

                result["channels"] += 1
                response = self.request(
                    "POST",
                    f"/channels/{channel_id}/messages/{last_message_id}/ack",
                    data={"token": None, "manual": True},
                )
                if response is not None and getattr(response, "status_code", None) in (200, 204):
                    result["acked"] += 1
                else:
                    result["channels_failed"] += 1

        return result

    def get_channels(self, guild_id: str, force: bool = False) -> List[Dict[str, Any]]:
        if not force:
            cached = self.cache.get_channels(guild_id)
            if cached:
                return cached

        response = self.request("GET", f"/guilds/{guild_id}/channels")
        if response and response.status_code == 200:
            channels = response.json()
            self.cache.save_channels(guild_id, channels)
            return channels
        return []

    def get_dm_channels(self, force: bool = False) -> List[Dict[str, Any]]:
        endpoint = "/users/@me/channels"
        if force:
            self._response_cache.pop(endpoint, None)
        response = self.request("GET", endpoint)
        return response.json() if response and response.status_code == 200 else []

    def get_friends(self, force: bool = False) -> List[Dict[str, Any]]:
        endpoint = "/users/@me/relationships"
        if force:
            self._response_cache.pop(endpoint, None)
        response = self.request("GET", endpoint)
        return response.json() if response and response.status_code == 200 else []

    def get_known_user(self, user_id: str, force: bool = False) -> Optional[Dict[str, Any]]:
        target_id = str(user_id or "").strip()
        if not target_id:
            return None

        for channel in self.get_dm_channels(force=force):
            recipients = channel.get("recipients") or []
            for recipient in recipients:
                if str(recipient.get("id") or "") == target_id:
                    return recipient

        for relationship in self.get_friends(force=force):
            user_obj = relationship.get("user") or {}
            if str(user_obj.get("id") or "") == target_id:
                return user_obj

        response = self.request("GET", f"/users/{target_id}")
        if response and response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                return payload

        profile_response = self.request("GET", f"/users/{target_id}/profile?with_mutual_guilds=false")
        if profile_response and profile_response.status_code == 200:
            payload = profile_response.json()
            if isinstance(payload, dict):
                user_obj = payload.get("user")
                if isinstance(user_obj, dict):
                    return user_obj

        return None

    def add_friend(self, user_id: str) -> bool:
        response = self.request("POST", f"/users/@me/relationships/{user_id}")
        return response.status_code == 204 if response else False

    def block_user(self, user_id: str) -> bool:
        response = self.request(
            "PUT",
            f"/users/@me/relationships/{user_id}",
            data={"type": int(RelationshipType.Blocked)},
        )
        return response.status_code == 204 if response else False
    # ── Slash / Interaction API (ported from KrishnaSS