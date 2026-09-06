#!/usr/bin/env python3
"""
Generic same-translation-unit guard test.

  python guard_test.py <ue_source_file> <GUARD_SUBSTR>

Splits the file's TEXT("...") literals into inside-guard vs outside-guard, then
searches both sets in the SUPERVIVE dumps. Outside-guard literals are the
control (same TU, same .rdata neighbourhood); inside-guard literals are the test.
The only variable is guard membership.
"""
import os
import re
import sys

IMAGES = [
    ("tutorial-hero (.rdata 100%)", r"dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe"),
]

IF = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$')
TXT = re.compile(r'TEXT\(\s*"((?:[^"\\]|\\.){8,80})"\s*\)')


def split_literals(path, guard):
    lines = open(path, encoding='utf-8', errors='replace').readlines()
    stack, depth = [], 0
    inside, outside = [], []
    for n, ln in enumerate(lines, 1):
        m = IF.match(ln)
        if m:
            k, e = m.group(1), m.group(2)
            if k in ('if', 'ifdef', 'ifndef'):
                g = guard in e
                stack.append(g)
                if g:
                    depth += 1
            elif k in ('elif', 'else'):
                if stack and stack[-1]:
                    depth -= 1
                    stack[-1] = False
            elif k == 'endif':
                if stack and stack.pop():
                    depth -= 1
            continue
        for lit in TXT.findall(ln):
            if '\\' in lit or '%' == lit.strip():
                continue
            (inside if depth > 0 else outside).append((n, lit))
    # dedupe preserving order
    def dd(seq):
        seen, out = set(), []
        for n, l in seq:
            if l not in seen:
                seen.add(l)
                out.append((n, l))
        return out
    return dd(inside), dd(outside)


def present(blob, s):
    return (blob.find(s.encode('utf-16-le')) >= 0) or (blob.find(s.encode('ascii', 'replace')) >= 0)


def main():
    src, guard = sys.argv[1], sys.argv[2]
    inside, outside = split_literals(src, guard)
    print(f"source : {os.path.basename(src)}")
    print(f"guard  : #if {guard}")
    print(f"inside : {len(inside)} unique literals   outside: {len(outside)} unique literals")
    print()

    for label, path in IMAGES:
        blob = open(path, 'rb').read()
        print("=" * 74)
        print(f"IMAGE: {label}")
        print()
        print(f"  CONTROL — outside the guard (expect mostly PRESENT):")
        cp = 0
        for n, l in outside[:14]:
            p = present(blob, l)
            cp += p
            print(f"    [{'PRESENT' if p else 'absent '}] L{n:<5} {l[:60]!r}")
        cn = min(14, len(outside))
        print(f"    -> {cp}/{cn} present")
        print()
        print(f"  TEST — inside the guard:")
        tp = 0
        for n, l in inside[:14]:
            p = present(blob, l)
            tp += p
            print(f"    [{'PRESENT' if p else 'absent '}] L{n:<5} {l[:60]!r}")
        tn = min(14, len(inside))
        print(f"    -> {tp}/{tn} present")
        print()
        if cp == 0:
            print("  VERDICT: VOID — controls absent, method cannot see this TU.")
        elif tp == 0:
            print(f"  VERDICT: guard evaluated FALSE — block COMPILED OUT "
                  f"({cp}/{cn} controls present, 0/{tn} tests).")
        elif tp == tn:
            print(f"  VERDICT: guard evaluated TRUE — block compiled IN.")
        else:
            print(f"  VERDICT: MIXED ({tp}/{tn}) — inspect individually; "
                  f"some literals may be shared/pooled.")
        print()


if __name__ == '__main__':
    main()
