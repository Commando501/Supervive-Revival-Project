#!/usr/bin/env python
"""LANE X1 (S138): sweep CLAUDE.md + docs/**.md for 'this page is dark'
claims tied to a concrete .text RVA, and re-grade each against merged13.

Written 2026-08-21.  scratchpad/s138/lanex1/sweep_dark_claims.py.  Read-only.
Emits TSV on stdout: status<TAB>file<TAB>line<TAB>rva<TAB>nz<TAB>keyword<TAB>text
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pagegrade import Image

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
IMG = Image(os.path.join(ROOT, 'dumps/merged13.dump.exe'))

TEXT_LO, TEXT_HI = 0x1000, 0x1000 + 0x7649000

# Each pattern is a claim that a concrete address's CODE is not readable.
CLAIM_PATTERNS = [
    (r'\bDARK\b',                          'DARK'),
    (r'\bdark\b(?=[^a-z])',                'dark'),
    (r'COVERAGE[- ]BLOCKED',               'COVERAGE-BLOCKED'),
    (r'coverage[- ]blocked',               'coverage-blocked'),
    (r'never (?:demand-)?decrypted',       'never-decrypted'),
    (r'not (?:yet )?(?:demand-)?decrypted', 'not-decrypted'),
    (r'undecrypted',                       'undecrypted'),
    (r'all[- ]zero page',                  'all-zero-page'),
    (r'\ban all-zero\b',                   'all-zero'),
    (r'0\s*/\s*4096',                      '0/4096'),
    (r'(?:not|un)readable offline',        'unreadable-offline'),
    (r'zero page',                         'zero-page'),
    (r'IMPL-PAGE-DARK',                    'IMPL-PAGE-DARK'),
    (r'100\s*%\s*zero',                    '100%-zero'),
    (r'zero in (?:every|all) (?:dump|image)', 'zero-in-every-image'),
    (r'all-zero in \d+ of \d+ images',     'all-zero-in-N'),
]
CLAIM_RE = [(re.compile(p), k) for p, k in CLAIM_PATTERNS]
HEX_RE = re.compile(r'0x([0-9A-Fa-f]{4,9})\b')

files = [os.path.join(ROOT, 'CLAUDE.md')]
for dp, dn, fn in os.walk(os.path.join(ROOT, 'docs')):
    for f in sorted(fn):
        if f.endswith('.md'):
            files.append(os.path.join(dp, f))

rows = []
for path in files:
    try:
        lines = open(path, 'r', encoding='utf-8', errors='replace').read().split('\n')
    except OSError:
        continue
    rel = os.path.relpath(path, ROOT).replace(chr(92), '/')
    for i, line in enumerate(lines, 1):
        kws = [k for rx, k in CLAIM_RE if rx.search(line)]
        if not kws:
            continue
        addrs = []
        for m in HEX_RE.finditer(line):
            v = int(m.group(1), 16)
            if TEXT_LO <= v < TEXT_HI:
                addrs.append(v)
        if not addrs:
            continue
        for v in sorted(set(addrs)):
            r = IMG.page_nonzero(v)
            nz = r[0] if r else -1
            rows.append((('STILL-DARK' if nz == 0 else 'NOW-LIT'), rel, i, v, nz,
                         '|'.join(sorted(set(kws))), line.strip()))

print('status\tfile\tline\trva\tnz4096\tkeyword\ttext')
for r in rows:
    print('%s\t%s\t%d\t0x%08X\t%d\t%s\t%s' % (r[0], r[1], r[2], r[3], r[4], r[5], r[6][:400]))
print('\n# TOTALS: rows=%d  NOW-LIT=%d  STILL-DARK=%d  distinct-RVAs=%d  files=%d' % (
    len(rows), sum(1 for r in rows if r[0] == 'NOW-LIT'),
    sum(1 for r in rows if r[0] == 'STILL-DARK'),
    len(set(r[3] for r in rows)), len(set(r[1] for r in rows))), file=sys.stderr)
