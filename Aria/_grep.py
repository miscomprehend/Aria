import sys, re

path = sys.argv[1]
pattern = sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    for i, line in enumerate(fh, 1):
        if re.search(pattern, line, re.IGNORECASE):
            print(f"{i:5d}| {line.rstrip()}")