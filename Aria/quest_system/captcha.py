"""Captcha solving module."""

import os
from typing import Optional, Dict, Any
from .interface import CaptchaDataFromRequest
from .constants import Constants

# Import captcha solver if available
try:
    from .providers.nocaptcha import NoCaptchaSolver
    _nocaptcha_available = True
except ImportError:
    _nocaptcha_available = False
    NoCaptchaSolver = None

try:
    from .providers.yescaptcha import YesCaptchaSolver
    _yescaptcha_available = True
except ImportError:
    _yescaptcha_available = False
    YesCaptchaSolver = None


class CaptchaSolver:
    """Handles captcha solving for quests."""

    def __init__(self):
        """Initialize captcha solver."""
        self._solver: Optional[Any] = None
        self._provider_name: Optional[str] = None

        nocaptcha_key = os.environ.get('NOCAPTCHAAI_API_KEY')
        if nocaptcha_key and _nocaptcha_available and NoCaptchaSolver:
            try:
                self._solver = NoCaptchaSolver(nocaptcha_key)
                self._provider_name = 'NoCaptchaAI'
            except Exception as e:
                print(f"Failed to initialize NoCaptchaAI: {e}")

        if self._solver is None:
            yescaptcha_key = os.environ.get('YES_CAPTCHA_API_KEY')
            if yescaptcha_key and _yescaptcha_available and YesCaptchaSolver:
                try:
                    self._solver = YesCaptchaSolver(yescaptcha_key)
                    self._provider_name = 'YesCaptcha'
                except Exception as e:
                    print(f"Failed to initialize YesCaptcha: {e}")

    async def solve_captcha(self, data: CaptchaDataFromRequest) -> str:
        """Solve hCaptcha using NoCaptchaAI or YesCaptcha.
        
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
            result = await self._solver.hcaptcha(
                data.captcha_sitekey,
                'https://discord.com',
                {
                    'rqdata': data.captcha_rqdata,
                    'isInvisible': False,
                    'userAgent': Constants.USER_AGENT,
                }
            )
            return result.get('gRecaptchaResponse', '')
        except Exception as e:
            provider = self._provider_name or 'captcha provider'
            raise ValueError(f"Failed to solve captcha with {provider}: {e}")

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
