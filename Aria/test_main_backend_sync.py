import symtable
from pathlib import Path


def test_main_does_not_shadow_module_sys_in_command_closures():
    source = (Path(__file__).resolve().parent / "main.py").read_text(encoding="utf-8")
    module_scope = symtable.symtable(source, "main.py", "exec")
    main_scope = next(scope for scope in module_scope.get_children() if scope.get_name() == "main")

    assert not main_scope.lookup("sys").is_local()


def test_main_backend_has_one_utility_category_and_exposes_quest():
    source = (Path(__file__).resolve().parent / "main.py").read_text(encoding="utf-8")

    assert source.count('"utility": {') == 1, "Duplicate utility help entries remain in main.py"
    assert '@bot.command(name="quest"' in source, "Quest command is missing from main.py"
    assert "QuestSystem" in source, "Quest manager is not initialized in main.py"
    assert "backend_category_targets" in source, "Backend help categories are not wired into main.py"
    assert "backend_help_per_page" in source, "Backend help pagination is not used by main.py"


def test_main_profile_command_is_separate_from_user_lookup():
    source = (Path(__file__).resolve().parent / "main.py").read_text(encoding="utf-8")

    assert '@bot.command(name="profile", aliases=["myprofile"])' in source
    assert '@bot.command(name="userinfo", aliases=["whois", "lookup"])' in source


def test_hostbot_banner_matches_requested_wordmark():
    from aria_backend.hostbot import BANNER

    assert BANNER == [
        "█████  ██████  ██  █████",
        "██   ██ ██   ██ ██ ██   ██",
        "███████ ██████  ██ ███████",
        "██   ██ ██   ██ ██ ██   ██",
        "██   ██ ██   ██ ██ ██   ██",
    ]
