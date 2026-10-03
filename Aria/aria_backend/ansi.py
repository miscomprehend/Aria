RESET = "\u001b[0m"
BOLD = "\u001b[1m"
UNDERLINE = "\u001b[4m"

DARK = "\u001b[30m"
WHITE = "\u001b[0;37m"
CYAN = "\u001b[0;36m"
PURPLE = "\u001b[0;35m"
BLUE = "\u001b[0;34m"
GREEN = "\u001b[0;32m"
RED = "\u001b[0;31m"
YELLOW = "\u001b[0;33m"
PINK = "\u001b[1;35m"

NAME = "Aria"
VERSION = "v2.0.0"
AUTHOR = "Misconsideration"


def _block(content: str) -> str:
    return quote_block(f"```ansi\n{content}\n```")


def quote_block(content: str) -> str:
    return "\n".join(f"> {line}" for line in content.split("\n"))


def format_message(title: str, content: str = "", status: str | None = None) -> str:
    symbols = {
        "error": f"{RED}✗{RESET}",
        "success": f"{GREEN}✓{RESET}",
        "info": f"{CYAN}ℹ{RESET}",
    }
    result = f"{symbols.get(status, f'{PURPLE}•{RESET}')} {BOLD}{title}{RESET}"
    return f"{result}\n{content}" if content else result


def _raw_header(subtitle: str) -> str:
    return (
        f"{PINK}{BOLD}{UNDERLINE}{NAME}{RESET}{DARK} :: {RESET}"
        f"{GREEN}{VERSION}{DARK} :: {RESET}{PINK}{subtitle}{RESET}"
    )


def header(subtitle: str) -> str:
    return _raw_header(subtitle)


def category_list(categories: dict) -> str:
    lines = []
    for name, desc in categories.items():
        lines.append(f"{PURPLE}{name:<10}{DARK}:: {RESET}{WHITE}{desc}{RESET}")
    return "\n".join(lines)


def footer_main() -> str:
    return f"{DARK}Developed by {WHITE}{AUTHOR}{RESET}"


def footer_page(prefix: str, category: str, page: int, total: int) -> str:
    return f"{prefix}help {category.lower()} | page {page}/{total}"


def command_list(cmds: list) -> str:
    lines = []
    for name, desc in cmds:
        lines.append(f"{CYAN}{name:<13}{DARK}:: {RESET}{WHITE}{desc}{RESET}")
    return "\n".join(lines)


def command_usage(name: str, usage: str, description: str, prefix: str) -> str:
    title = _raw_header(name.upper())
    body = (
        f"{CYAN}{'Command':<13}{DARK}:: {RESET}{WHITE}{name}{RESET}\n"
        f"{CYAN}{'Usage':<13}{DARK}:: {RESET}{WHITE}{prefix}{usage}{RESET}\n"
        f"{CYAN}{'Description':<13}{DARK}:: {RESET}{WHITE}{description}{RESET}"
    )
    return _block(title) + "\n" + _block(body)


def success(msg: str) -> str:
    return f"{GREEN}✓ {msg}{RESET}"


def error(msg: str) -> str:
    return f"{RED}✗ {msg}{RESET}"


def warning(msg: str) -> str:
    return f"{YELLOW}⚠ {msg}{RESET}"


def status_bar(label: str, value: str, max_width: int = 40) -> str:
    return f"{CYAN}{label:<15}{DARK}:: {RESET}{WHITE}{str(value)[:max_width]}{RESET}"


def status_box(title: str, details: dict) -> str:
    lines = [_raw_header(str(title)), ""]
    lines.extend(
        f"{CYAN}{key:<15}{DARK}:: {RESET}{WHITE}{str(value)}{RESET}"
        for key, value in details.items()
    )
    return _block("\n".join(lines))


def nitro_status(status: str, claimed: int, cached: int, last_claimed=None) -> str:
    return status_box("Nitro", {
        "Status": str(status),
        "Claimed": str(claimed),
        "Cached": str(cached),
        "Last Claimed": str(last_claimed or "never"),
    })


def giveaway_status(status: str, entered: int, won: int, failed: int, last_win=None) -> str:
    return status_box("Giveaway", {
        "Status": str(status),
        "Entered": str(entered),
        "Won": str(won),
        "Failed": str(failed),
        "Last Win": str(last_win or "never"),
    })


def info_block(title: str, body: str) -> str:
    return _block(f"{_raw_header(str(title))}\n\n{WHITE}{body}{RESET}")


def command_page(title: str, lines: list, footer: str = "") -> str:
    body = [*_command_lines(lines)]
    if footer:
        body.extend(["", f"{DARK}{footer}{RESET}"])
    return _block(f"{_raw_header(title)}\n\n" + "\n".join(body))


def _command_lines(lines: list) -> list[str]:
    return [f"{CYAN}{name:<13}{DARK}:: {RESET}{WHITE}{desc}{RESET}" for name, desc in lines]


def _compose(*sections) -> str:
    return _block("\n".join(str(section) for section in sections if section))


def layout(header_text: str, body_text: str, footer_text: str) -> str:
    return "\n".join((
        _block(_raw_header(header_text)),
        _block(body_text),
        _block(f"{DARK}{footer_text}{RESET}"),
    ))


def sections(header_text: str, body_text: str, footer_text: str = "") -> str:
    parts = [_block(_raw_header(header_text)), _block(body_text)]
    if str(footer_text or "").strip():
        parts.append(_block(str(footer_text)))
    return "\n".join(parts)


def panel(header_text: str, body_text: str = "", footer_text: str = "") -> str:
    parts = [_raw_header(header_text)]
    if str(body_text or "").strip():
        parts.extend(["", str(body_text)])
    if str(footer_text or "").strip():
        parts.extend(["", str(footer_text)])
    return _block("\n".join(parts))


def paginate(content: list, page: int, per_page: int = 10):
    if per_page < 1:
        raise ValueError("per_page must be positive")
    total_pages = max(1, (len(content) + per_page - 1) // per_page)
    page = max(1, min(int(page), total_pages))
    start = (page - 1) * per_page
    return content[start:start + per_page], total_pages
