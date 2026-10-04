"""Captcha solving providers."""

from .nocaptcha import NoCaptchaSolver
from .yescaptcha import YesCaptchaSolver

__all__ = ['NoCaptchaSolver', 'YesCaptchaSolver']
