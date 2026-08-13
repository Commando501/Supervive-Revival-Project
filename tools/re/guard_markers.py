#!/usr/bin/env python3
"""
Extract string literals that live ONLY inside a named preprocessor guard in the
stock UE source tree, and (critically) that do NOT also appear outside it.

Why: FK-13 was created by an uncontrolled string scan. A literal that is emitted
by UHT, or that also occurs in unguarded code, tells you nothing about whether a
guarded block compiled. A literal that occurs ONLY inside `#if ALLOW_CONSOLE`
(and nowhere else in the engine) is a direct, controlled presence test.

Usage:
  python guard_markers.py <GUARD_EXPR_SUBSTRING> [more...]
e.g.
  python guard_markers.py ALLOW_CONSOLE
  python guard_markers.py "!UE_BUILD_SHIPPING"
"""
import os
import re
import sys
from collections import defaultdict

UE_ROOT = r"H:/Unreal Engine/UE_5.4/Engine/Source"

IF_RE = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$')
# TEXT("...") and plain "..." literals of reasonable length
TEXT_RE = re.compile(r'TEXT\(\s*"((?:[^"\\]|\\.){4,80})"\s*\)')

SRC_EXT = ('.cpp', '.h', '.inl')


def scan_file(path, guard_sub):
    """Return (inside_literals, outside_literals) for one file."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
    except OSError:
        return set(), set()

    inside, outside = set(), set()
    # stack of (is_guard_region_bool); depth-tracked
    stack = []
    guard_depth = 0  # >0 means we are inside at least one matching guard

    for ln in lines:
        m = IF_RE.match(ln)
        if m:
            kind, expr = m.group(1), m.group(2)
            if kind in ('if', 'ifdef', 'ifndef'):
                is_guard = guard_sub in expr
                stack.append(is_guard)
                if is_guard:
                    guard_depth += 1
            elif kind in ('elif', 'else'):
                # leaving the guarded branch of this level
                if stack and stack[-1]:
                    guard_depth -= 1
                    stack[-1] = False
            elif kind == 'endif':
                if stack:
                    was = stack.pop()
                    if was:
                        guard_depth -= 1
            continue

        for lit in TEXT_RE.findall(ln):
            (inside if guard_depth > 0 else outside).add(lit)

    return inside, outside


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    guard_sub = sys.argv[1]

    files = []
    for root, dirs, names in os.walk(UE_ROOT):
        dirs[:] = [d for d in dirs if d not in ('ThirdParty', 'Intermediate')]
        for n in names:
            if n.endswith(SRC_EXT):
                files.append(os.path.join(root, n))

    all_inside = defaultdict(set)   # literal -> set(files where inside guard)
    all_outside = set()             # literals seen anywhere outside the guard

    hit_files = 0
    for p in files:
        # cheap pre-filter: only parse files that mention the guard at all,
        # but still collect their outside-literals for the exclusion set.
        try:
            with open(p, 'r', encoding='utf-8', errors='replace') as fh:
                blob = fh.read()
        except OSError:
            continue
        if guard_sub not in blob:
            # still harvest literals for the global exclusion set
            for lit in TEXT_RE.findall(blob):
                all_outside.add(lit)
            continue
        hit_files += 1
        ins, outs = scan_file(p, guard_sub)
        for lit in ins:
            all_inside[lit].add(os.path.relpath(p, UE_ROOT))
        all_outside |= outs

    exclusive = {lit: fs for lit, fs in all_inside.items() if lit not in all_outside}

    print(f"guard: {guard_sub!r}")
    print(f"files scanned: {len(files)}   files containing guard: {hit_files}")
    print(f"literals inside guard: {len(all_inside)}   "
          f"EXCLUSIVE to guard (never seen outside anywhere): {len(exclusive)}")
    print()
    print("=== EXCLUSIVE MARKER LITERALS (usable as a controlled presence test) ===")
    for lit, fs in sorted(exclusive.items(), key=lambda kv: -len(kv[0])):
        srcs = ', '.join(sorted(fs)[:2])
        print(f"  {lit!r}   [{srcs}]")
    return 0


if __name__ == '__main__':
    sys.exit(main())
