"""Captcha solving providers."""

from .nocaptcha import NoCaptchaSolver
from .twocaptcha import TwoCaptchaSolver
from .yescaptcha import TwoCaptchaCompatibleSolver, YesCaptchaSolver

__all__ = ['NoCaptchaSolver', 'YesCaptchaSolver', 'TwoCaptchaCompatibleSolver', 'TwoCaptchaSolver']
