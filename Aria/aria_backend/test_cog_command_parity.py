import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent


def _decorated_names(path: Path, decorator_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != decorator_name:
                continue
            name = node.name
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    name = keyword.value.value
            names.append(name)
    return names


def _slash_command_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "command"
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "tree"
            ):
                names.extend(
                    keyword.value.value
                    for keyword in decorator.keywords
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant)
                )
    return names


class CogCommandParityTests(unittest.TestCase):
    def test_every_cog_command_has_one_slash_command(self):
        cog_commands = []
        for path in BACKEND_DIR.glob("*_cog.py"):
            cog_commands.extend(_decorated_names(path, "command"))

        slash_commands = _slash_command_names(BACKEND_DIR / "aria_backend.py")
        duplicates = sorted(
            name for name in set(slash_commands) if slash_commands.count(name) > 1
        )
        missing = sorted(set(cog_commands) - set(slash_commands))

        self.assertEqual(duplicates, [], f"Duplicate slash commands: {duplicates}")
        self.assertEqual(missing, [], f"Cog commands missing slash equivalents: {missing}")


if __name__ == "__main__":
    unittest.main()
