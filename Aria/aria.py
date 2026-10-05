#!/usr/bin/env python3
"""Aria formatter bootstrap launcher."""

from aria_entry import _use_utf8_console
from format_bootstrap import install_global_formatter
from main import main as bot_main


if __name__ == "__main__":
    _use_utf8_console()
    install_global_formatter()
    bot_main()
