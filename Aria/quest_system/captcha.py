"""Captcha solving module."""

import os
from typing import Optional, Dict, Any
from .interface import CaptchaDataFromRequest
from .constants import Constants

# Import captcha solver if available
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
        self._yescaptcha: Optional[Any] = None
        
        # Initialize YesCaptcha if API key is available
        api_key = os.environ.get('YES_CAPTCHA_API_KEY')
        if api_key and _yescaptcha_available and YesCaptchaSolver:
            try:
                self._yescaptcha = YesCaptchaSolver(api_key)
            except Exception as e:
                print(f"Failed to initialize YesCaptcha: {e}")

    async def solve_captcha(self, data: CaptchaDataFromRequest) -> str:
        """Solve hCaptcha using YesCaptcha.
        
        Args:
            data: Captcha data from Discord
            
        Returns:
            Captcha solution token
            
        Raises:
            ValueError: If solving fails or is not available
        """
        if not self._yescaptcha:
            raise ValueError('Captcha solving not available')
        
        try:
            result = await self._yescaptcha.hcaptcha(
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
            raise ValueError(f"Failed to solve captcha: {e}")

    def is_available(self) -> bool:
        """Check if captcha solving is available."""
        return self._yescaptcha is not None


# Global solver instance
_solver: Optional[CaptchaSolver] = None


def get_captcha_solver() -> CaptchaSolver:
    """Get or create captcha solver instance."""
    global _solver
    if _solver is None:
        _solver = CaptchaSolver()
    return _solver
