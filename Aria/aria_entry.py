"""Entry point for source runs and the frozen Windows application."""

import os
import runpy
import sys


def _use_utf8_console():
    # Legacy Windows code pages cannot encode the emoji/symbols Aria prints.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleTitleW("Aria")
            _set_windows_console_font()
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    _install_safe_print()


def _set_windows_console_font(face_name="Cascadia Mono", height=16):
    """Switch the attached console to a font that can draw Unicode.

    Raster fonts stay selected on some Windows terminals even after the code
    page is UTF-8, so symbols still fail to render. Missing fonts are ignored.
    """
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.SetCurrentConsoleFontEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
    ]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    class _Coord(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _FontInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("nFont", ctypes.c_ulong),
            ("dwFontSize", _Coord),
            ("FontFamily", ctypes.c_uint),
            ("FontWeight", ctypes.c_uint),
            ("FaceName", ctypes.c_wchar * 32),
        ]

    handle = kernel32.CreateFileW(
        "CONOUT$",
        0x80000000 | 0x40000000,
        0x1 | 0x2,
        None,
        3,
        0,
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        return
    try:
        font = _FontInfo()
        font.cbSize = ctypes.sizeof(_FontInfo)
        font.dwFontSize = _Coord(0, height)
        font.FontFamily = 54
        font.FontWeight = 400
        font.FaceName = face_name
        kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(font))
    finally:
        kernel32.CloseHandle(handle)


def _install_safe_print():
    """Keep print() alive when a stream still cannot encode a character."""
    import builtins

    if getattr(builtins, "_aria_safe_print", False):
        return
    original = builtins.print

    def safe_print(*args, **kwargs):
        try:
            original(*args, **kwargs)
        except UnicodeEncodeError:
            file = kwargs.get("file", sys.stdout)
            encoding = getattr(file, "encoding", None) or "utf-8"
            safe_args = [
                str(arg).encode(encoding, "replace").decode(encoding, "replace")
                for arg in args
            ]
            original(*safe_args, **kwargs)

    builtins.print = safe_print
    builtins._aria_safe_print = True


def main():
    _use_utf8_console()
    if getattr(sys, "frozen", False):
        os.chdir(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))

    if len(sys.argv) > 2 and sys.argv[1] == "--aria-run-script":
        script_path = os.path.abspath(sys.argv[2])
        sys.argv = [script_path, *sys.argv[3:]]
        runpy.run_path(script_path, run_name="__main__")
        return

    from main import main as run_aria

    run_aria()


if __name__ == "__main__":
    main()