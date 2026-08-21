#!/usr/bin/env python3
# LANE 3 (c) -- attribute the .text pages that were DECRYPTED at some crash
# (per the minidump MemoryInfoList) but are ZERO in the best merged image.
# Those are pages whose plaintext existed in a process we snapshotted only as a
# minidump (which captures 0 image bytes), so they are IDENTIFIED but NOT RECOVERED.
#
# Usage: python gap41.py <root> <merged.dump.exe>

import os, sys, collections
from text_pagemap import pagemap, TEXT_RVA, TEXT_VSZ, PAGE, NTEXT, NOACCESS


def main():
    root, merged = sys.argv[1], sys.argv[2]
    with open(merged, 'rb') as f:
        f.seek(TEXT_RVA)
        blob = f.read(TEXT_VSZ)
    mset = set(pg for pg in range(NTEXT) if any(blob[pg * PAGE:(pg + 1) * PAGE]))

    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    perguid = {}
    for p in files:
        res = pagemap(p)
        if res is None:
            continue
        prot = res[0]
        dec = set(pg for pg, pv in prot.items() if pv != NOACCESS)
        g = os.path.basename(p)
        if g not in perguid or len(dec) > len(perguid[g][0]):
            perguid[g] = (dec, p)
    union = set()
    for dec, p in perguid.values():
        union |= dec
    gap = union - mset
    print('distinct crashes            : %d' % len(perguid))
    print('union decrypted pages       : %d' % len(union))
    print('merged non-zero pages       : %d' % len(mset))
    print('GAP (decrypted, never dumped): %d pages = %d bytes' % (len(gap), len(gap) * PAGE))
    contrib = collections.Counter()
    for g, (dec, p) in perguid.items():
        c = len(dec & gap)
        if c:
            contrib[p] = c
    print('')
    print('contributing crashes:')
    for p, c in contrib.most_common(20):
        print('   %5d pages  %s' % (c, p))
    print('')
    print('GAP page RVAs (all %d):' % len(gap))
    gl = sorted(gap)
    for i in range(0, len(gl), 10):
        print('   ' + ' '.join('0x%X' % (TEXT_RVA + x * PAGE) for x in gl[i:i + 10]))
    # contiguous runs
    runs = []
    s = None
    prev = None
    for x in gl:
        if s is None:
            s = prev = x
            continue
        if x == prev + 1:
            prev = x
        else:
            runs.append((s, prev))
            s = prev = x
    if s is not None:
        runs.append((s, prev))
    print('')
    print('contiguous runs: %d' % len(runs))
    for a, b in runs:
        print('   0x%X..0x%X  (%d pages)' % (TEXT_RVA + a * PAGE, TEXT_RVA + b * PAGE + PAGE - 1, b - a + 1))


if __name__ == '__main__':
    main()
