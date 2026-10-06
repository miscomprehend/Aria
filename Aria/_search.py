import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
pattern = re.compile(sys.argv[2], re.IGNORECASE)

for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git", "node_modules", "build", "dist"}]
    for name in filenames:
        if not name.endswith((".py", ".js", ".html", ".json", ".md")):
            continue
        path = os.path.join(dirpath, name)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if pattern.search(line):
                        print(f"{path}:{i}: {line.rstrip()[:160]}")
        except Exception:
            pass
