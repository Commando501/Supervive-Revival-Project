# scan_strings.py — find ASCII + UTF-16LE strings matching a pattern in a binary (e.g. an unpacked image dump).
#   usage: scan_strings.py <file> <regex> [maxhits]
# Used S94 to hunt fog-of-war console variables / flag names in dumps/merged.dump.exe.
import re, sys

path = sys.argv[1]
pat = re.compile(sys.argv[2].encode("latin1"), re.I)
maxhits = int(sys.argv[3]) if len(sys.argv) > 3 else 200

data = open(path, "rb").read()
print(f"{len(data)/1048576:.0f} MB scanned")

def emit(kind, seen, s, off):
    key = (kind, s)
    if key in seen:
        return False
    seen.add(key)
    print(f"[{kind}] @0x{off:X}  {s}")
    return True

seen = set()
n = 0

# ASCII runs
for m in re.finditer(rb"[\x20-\x7e]{5,120}", data):
    s = m.group()
    if pat.search(s):
        if emit("A", seen, s.decode("latin1"), m.start()):
            n += 1
            if n >= maxhits:
                break

# UTF-16LE runs (char + \x00)
if n < maxhits:
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,120}", data):
        s = m.group()[::2]
        if pat.search(s):
            if emit("W", seen, s.decode("latin1"), m.start()):
                n += 1
                if n >= maxhits:
                    break

print(f"-- {n} unique hits --")
