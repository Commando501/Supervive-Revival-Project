#!/usr/bin/env python3
"""
Enumerate candidate console-variable / console-command NAMES in the shipping image.

Why this matters: UKismetSystemLibrary::ExecuteConsoleCommand tries
IConsoleManager::Get().ProcessUserConsoleInput() FIRST, before any PlayerController
routing. Anything registered there is reachable with no instance, no pawn, no
override -- and cvars are additionally settable shim-free via the [ConsoleVariables]
section of a user ini, a mechanism this project already uses.

Method: cvar/ccmd names are UTF-16LE literals in .rdata with a very specific shape --
dotted, no spaces, ASCII-printable, moderate length. We harvest by shape and then
group by prefix. Shape-matching over-collects (any dotted token qualifies), so the
output is CANDIDATES, and the Loki-owned prefixes are what matter.

Controls: five cvar names independently confirmed present this session
(console.position.enable, con.MinLogVerbosity, ...) plus the four the shipped
DefaultEngine.ini [ConsoleVariables]/[SystemSettings] sections actually set --
p.NetPackedMovementMaxBits, net.AllowAsyncLoading, net.MaxRPCPerNetUpdate,
net.DelayUnmappedRPCs, net.IpConnectionUseSendTasks. If those do not appear, the
harvester is broken and every count below is void.
"""
import re
import sys
from collections import Counter, defaultdict

IMG = r"dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe"
RDATA_LO, RDATA_HI = 0x764A000, 0x764A000 + 0x237D000

CONTROLS = [
    "console.position.enable", "con.MinLogVerbosity",
    "p.NetPackedMovementMaxBits", "net.AllowAsyncLoading",
    "net.MaxRPCPerNetUpdate", "net.DelayUnmappedRPCs",
    "net.IpConnectionUseSendTasks",
]

# A dotted identifier: seg(.seg)+ , each seg alnum/underscore, total 6..60
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$')


def harvest_wide(blob, lo, hi):
    """Yield (offset, text) for NUL-terminated UTF-16LE ASCII-range strings."""
    out = []
    i = lo
    end = min(hi, len(blob) - 1)
    while i < end - 1:
        # candidate start: ascii letter followed by 0x00
        if blob[i + 1] == 0 and 0x41 <= blob[i] <= 0x7A:
            j = i
            chars = []
            while j < end - 1 and blob[j + 1] == 0 and 0x20 <= blob[j] <= 0x7E:
                chars.append(chr(blob[j]))
                j += 2
            if j < end - 1 and blob[j] == 0 and blob[j + 1] == 0 and len(chars) >= 6:
                s = ''.join(chars)
                if len(s) <= 60:
                    out.append((i, s))
                i = j + 2
                continue
        i += 2
    return out


def main():
    blob = open(IMG, 'rb').read()
    print(f"image  : {IMG} ({len(blob):,} bytes)")
    print(f"scanned: .rdata 0x{RDATA_LO:X}-0x{RDATA_HI:X} (100% readable per manifest)")
    print()

    strings = harvest_wide(blob, RDATA_LO, RDATA_HI)
    print(f"wide ASCII-range strings harvested: {len(strings):,}")

    names = [(o, s) for o, s in strings if NAME_RE.match(s)]
    print(f"dotted-identifier shaped (cvar/ccmd candidates): {len(names):,}")
    print()

    found = {s for _, s in names}
    print("=== CONTROLS (must all be present, else output is VOID) ===")
    ok = 0
    for c in CONTROLS:
        hit = c in found
        ok += hit
        print(f"  [{'PRESENT' if hit else 'ABSENT '}] {c}")
    print(f"  -> {ok}/{len(CONTROLS)}")
    if ok == 0:
        print("\n  VOID: harvester found none of the known cvars. Stopping.")
        return 1
    print()

    prefixes = Counter(s.split('.')[0].lower() for _, s in names)
    print("=== top 30 prefixes by count ===")
    for p, n in prefixes.most_common(30):
        print(f"  {n:>5}  {p}")
    print()

    LOKI_PREFIXES = ('loki', 'lk', 'tc', 'theorycraft', 'ngs', 'dfl', 'ab', 'accelbyte')
    print("=== LOKI / TITLE-OWNED candidates ===")
    by_pref = defaultdict(list)
    for o, s in names:
        p = s.split('.')[0].lower()
        if p in LOKI_PREFIXES:
            by_pref[p].append((o, s))
    if not by_pref:
        print("  (none matched the title-prefix list)")
    for p in sorted(by_pref):
        rows = sorted(set(by_pref[p]), key=lambda t: t[1])
        print(f"\n  --- {p}.* ({len(rows)}) ---")
        for o, s in rows[:120]:
            print(f"    0x{o:08X}  {s}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
