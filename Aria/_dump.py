import sys

path = sys.argv[1]
start = int(sys.argv[2])
end = int(sys.argv[3])
with open(path, "r", encoding="utf-8") as fh:
    lines = fh.readlines()
for i in range(start - 1, min(end, len(lines))):
    print(f"{i+1:5d}| {lines[i].rstrip()}")
