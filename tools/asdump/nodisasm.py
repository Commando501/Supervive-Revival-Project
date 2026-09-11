#!/usr/bin/env python3
"""nodisasm.py -- print an asdump module .txt with the per-function
disassembly appendices stripped, so the pseudo-source reads end to end.

Read-only.  Usage:  python nodisasm.py <file.as.txt> [...]
"""
import sys

for p in sys.argv[1:]:
    skip = False
    for line in open(p, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.startswith("/* ---- "):
            skip = True
            continue
        if skip:
            if s == "*/":
                skip = False
            continue
        sys.stdout.write(line)
