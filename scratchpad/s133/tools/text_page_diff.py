#!/usr/bin/env python3
# LANE 3 (c) -- page-level .text coverage of EVERY on-disk source, and what each
# adds over the current best union.
#
# Sources handled:
#   *.dump.exe            (dumpimage / mergedumps output; .text at file offset 0x1000)
#   text_union.bin        (tools/re/.exec_surface_cache -- a raw 0x7649000-byte .text image)
#
# NOTE ON THE METRIC: a page is counted as PRESENT if any byte is non-zero. That is a
# FLOOR on "decrypted", because a decrypted page whose plaintext is all zeros reads as
# absent. It is the only byte-level metric available for a .dump.exe, because dumpimage
# zero-fills unread ranges and writes no per-page readability map (dumpimage.go:126,
# img := make([]byte, sizeOfImage)).
#
# Usage: python text_page_diff.py <base .dump.exe> <other> [<other> ...]

import os, sys

TEXT_RVA = 0x1000
TEXT_SIZE = 0x7649000
PAGE = 0x1000
NP = TEXT_SIZE // PAGE


def pages(path):
    sz = os.path.getsize(path)
    with open(path, 'rb') as f:
        if sz == TEXT_SIZE:          # raw .text image
            blob = f.read()
        else:
            f.seek(TEXT_RVA)
            blob = f.read(TEXT_SIZE)
    s = set()
    for pg in range(NP):
        if any(blob[pg * PAGE:(pg + 1) * PAGE]):
            s.add(pg)
    return s


def main():
    basep = sys.argv[1]
    base = pages(basep)
    print('BASE %s : %d / %d pages non-zero (%.2f%%)' % (basep, len(base), NP, 100.0 * len(base) / NP))
    print('')
    print('%-62s %8s %8s %8s' % ('SOURCE', 'PAGES', 'ADDS', 'ONLY-BASE'))
    acc = set(base)
    rows = []
    for p in sys.argv[2:]:
        if not os.path.exists(p):
            print('%-62s MISSING' % p)
            continue
        s = pages(p)
        rows.append((p, s))
        print('%-62s %8d %8d %8d' % (os.path.relpath(p), len(s), len(s - base), len(base - s)))
        acc |= s
    print('')
    print('UNION of base + all sources : %d / %d (%.2f%%)  -- adds %d pages over base'
          % (len(acc), NP, 100.0 * len(acc) / NP, len(acc - base)))
    extra = sorted(acc - base)
    if extra:
        print('pages ADDED over base (RVA):')
        for i in range(0, min(len(extra), 200), 12):
            print('   ' + ' '.join('0x%X' % (TEXT_RVA + g * PAGE) for g in extra[i:i + 12]))


if __name__ == '__main__':
    main()
