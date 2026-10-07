"""Captcha solving module."""

import inspect
import os
from typing import Optional, Any, Callable
from .interface import CaptchaDataFromRequest
from .constants import Constants


def _get_active_proxy_2captcha():
    """Return (proxy, proxytype) for 2Captcha from the shared ProxyManager, or ('', '')."""
    try:
        from proxy_manager import ProxyManager
        return ProxyManager().get_2captcha_proxy()
    except Exception:
        return "", ""


def _get_active_proxy_yescaptcha() -> str:
    """Return the active proxy in YesCaptcha 'type:host:port:user:pass' form, or ''."""
    try:
        from proxy_manager import ProxyManager
        return ProxyManager().get_yescaptcha_proxy()
    except Exception:
        return ""


try:
    from .providers.yescaptcha import YesCaptchaSolver
    _yescaptcha_available = True
except ImportError:
    _yescaptcha_available = False
    YesCaptchaSolver = None

try:
    from .providers.yescaptcha import TwoCaptchaCompatibleSolver
    _twocaptcha_compatible_available = True
except ImportError:
    _twocaptcha_compatible_available = False
    TwoCaptchaCompatibleSolver = None

try:
    from .providers.twocaptcha import TwoCaptchaSolver
    _twocaptcha_available = True
except ImportError:
    _twocaptcha_available = False
    TwoCaptchaSolver = None


# Import captcha solver if available
try:
    from .providers.nocaptcha import NoCaptchaSolver
    _nocaptcha_available = True
except ImportError:
    _nocaptcha_available = False
    NoCaptchaSolver = None

def _accepts_rotate(func: Any, *args: Any) -> bool:
    """Return True when ``func`` can be called with a ``rotate`` keyword."""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    params = signature.parameters.values()
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
        return True
    return 'rotate' in signature.parameters


class CaptchaSolver:
    """Handles captcha solving for quests."""

    def __init__(self, rotate_callback: Optional[Callable[[], Any]] = None):
        """Initialize captcha solver.

        Args:
            rotate_callback: Optional callable invoked before each provider
                retry so the caller can rotate the browser/header profile.
                This keeps the request fingerprint in sync with a fresh task.
        """
        self._solver: Optional[Any] = None
        self._provider_name: Optional[str] = None
        self._rotate_callback = rotate_callback

        nocaptcha_key = str(os.environ.get('NOCAPTCHAAI_API_KEY') or "").strip()
        yescaptcha_key = str(os.environ.get('YES_CAPTCHA_API_KEY') or "").strip()
        configured_key = ""
        configured_provider = "nocaptchaai"
        configured_api_url = ""

        try:
            import config as aria_config
            settings = aria_config.Config()
            configured_key = str(settings.get("captcha_api_key") or "").strip()
            configured_provider = str(settings.get("captcha_provider") or "nocaptchaai").strip().lower()
            configured_api_url = str(settings.get("captcha_api_url") or "").strip()
            yescaptcha_key = yescaptcha_key or str(settings.get("yes_captcha_api_key") or "").strip()
        except Exception:
            pass

        if configured_key:
            if configured_provider == "yescaptcha":
                yescaptcha_key = yescaptcha_key or configured_key
            elif configured_provider == "twocaptcha":
                # Native 2Captcha by default; only fall back to the
                # YesCaptcha-compatible protocol when a custom API base URL is
                # supplied (i.e. a self-hosted or third-party compatible host).
                if configured_api_url and configured_api_url.rstrip("/") != "https://2captcha.com":
                    if _twocaptcha_compatible_available and TwoCaptchaCompatibleSolver:
                        try:
                            self._solver = TwoCaptchaCompatibleSolver(configured_key, configured_api_url)
                            self._provider_name = self._solver.provider_name
                        except Exception as error:
                            print(f"Failed to initialize compatible captcha provider: {error}")
                elif _twocaptcha_available and TwoCaptchaSolver:
                    try:
                        self._solver = TwoCaptchaSolver(configured_key)
                        self._provider_name = self._solver.provider_name
                    except Exception as error:
                        print(f"Failed to initialize 2Captcha: {error}")
            else:
                nocaptcha_key = nocaptcha_key or configured_key

        if self._solver is None and configured_provider == "twocaptcha" and configured_key:
            if not _twocaptcha_available and not _twocaptcha_compatible_available:
                print("2Captcha provider support is unavailable.")

        if self._solver is None and nocaptcha_key and _nocaptcha_available and NoCaptchaSolver:
            try:
                self._solver = NoCaptchaSolver(nocaptcha_key)
                self._provider_name = 'NoCaptchaAI'
            except Exception as e:
                print(f"Failed to initialize NoCaptchaAI: {e}")

        if self._solver is None:
            if yescaptcha_key and _yescaptcha_available and YesCaptchaSolver:
                try:
                    self._solver = YesCaptchaSolver(yescaptcha_key)
                    self._provider_name = 'YesCaptcha'
                except Exception as e:
                    print(f"Failed to initialize YesCaptcha: {e}")

    def set_rotate_callback(self, rotate_callback: Optional[Callable[[], Any]]) -> None:
        """Register a callback used to rotate headers before each retry."""
        self._rotate_callback = rotate_callback

    async def solve_captcha(self, data: CaptchaDataFromRequest) -> str:
        """Solve hCaptcha using the configured captcha provider.

        Args:
            data: Captcha data from Discord

        Returns:
            Captcha solution token

        Raises:
            ValueError: If solving fails or is not available
        """
        if not self._solver:
            raise ValueError('Captcha solving not available')

        try:
            options = {
                'rqdata': data.captcha_rqdata,
                'isInvisible': False,
                'userAgent': getattr(data, 'user_agent', None) or Constants.USER_AGENT,
            }

            # Pass the active proxy so the provider solves the challenge over
            # the same IP this session uses (2Captcha/YesCaptcha support it).
            proxy_kwargs = {}
            if self._provider_name == '2Captcha':
                proxy_str, _ = _get_active_proxy_2captcha()
                if proxy_str:
                    proxy_kwargs['proxy'] = proxy_str
            elif self._provider_name in {'YesCaptcha', '2Captcha-compatible provider'}:
                proxy_str = _get_active_proxy_yescaptcha()
                if proxy_str:
                    proxy_kwargs['proxy'] = proxy_str

            result = await self._solver.hcaptcha(
                data.captcha_sitekey,
                'https://discord.com/channels/@me',
                options=options,
                rotate=self._rotate_callback,
                **proxy_kwargs,
            )
            return result.get('gRecaptchaResponse', '')
        except Exception as e:
            provider = self._provider_name or 'captcha provider'
            raise ValueError(f"Failed to solve captcha with {provider}: {e}")

    async def solve_image_captcha(self, image_base64: str) -> str:
        """Solve image captcha and return extracted text.

        Passes the rotation callback through so the provider can rotate the
        browser/header profile (and TLS impersonation) between retries.
        """
        if not self._solver:
            raise ValueError('Captcha solving not available')

        if not hasattr(self._solver, 'image_captcha'):
            provider = self._provider_name or 'captcha provider'
            raise ValueError(f"Image captcha solving is not supported by {provider}")

        try:
            # Only pass ``rotate`` when the provider actually accepts it, so a
            # real TypeError raised inside the provider is never masked.
            if _accepts_rotate(self._solver.image_captcha):
                result = await self._solver.image_captcha(
                    image_base64, rotate=self._rotate_callback
                )
            else:
                result = await self._solver.image_captcha(image_base64)
        except Exception as e:
            provider = self._provider_name or 'captcha provider'
            raise ValueError(f"Failed to solve image captcha with {provider}: {e}")

        if not isinstance(result, dict):
            raise ValueError('Image captcha provider returned an invalid response')

        text = str(
            result.get('text')
            or result.get('captchaText')
            or result.get('answer')
            or ''
        ).strip()
        if not text:
            raise ValueError('Image captcha provider returned an empty solution')
        return text

    def is_available(self) -> bool:
        """Check if captcha solving is available."""
        return self._solver is not None


# Global solver instance
_solver: Optional[CaptchaSolver] = None


def get_captcha_solver() -> CaptchaSolver:
    """Get or create captcha solver instance."""
    global _solver
    if _solver is None:
        _solver = CaptchaSolver()
    return _solver
