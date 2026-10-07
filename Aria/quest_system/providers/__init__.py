"""Captcha solving providers."""

from .nocaptcha import NoCaptchaSolver
from .yescaptcha import TwoCaptchaCompatibleSolver, YesCaptchaSolver

__all__ = ['NoCaptchaSolver', 'YesCaptchaSolver', 'TwoCaptchaCompatibleSolver']
