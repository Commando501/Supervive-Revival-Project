#!/usr/bin/env python
"""ptrhunt.py -- who else holds this pointer?  READ-ONLY minidump search.

Searches every dumped memory range for an 8-byte value, reports 8-aligned hits
(pointer slots) separately from unaligned ones (byte-pattern coincidences), and
classifies each hit's containing range as stack / heap / module.

usage: ptrhunt.py <dump.dmp> 0xVAL [0xVAL ...]
"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdctx import MD


def classify(md, addr):
    mo = md.modof(addr)
    if mo:
        return "module %s+0x%X" % mo
    for t in md.threads:
        sa, sz, sr = t['stack']
        if sa <= addr < sa + sz:
            return "stack tid=%d (+0x%X)" % (t['tid'], addr - sa)
    return "heap"


def hunt(md, val):
    pat = struct.pack('<Q', val)
    aligned, unaligned = [], []
    stacks = set()
    for t in md.threads:
        stacks.add(t['stack'][2])
    for sa, sz, sr in md.ranges:
        blob = md.d[sr:sr + sz]
        i = blob.find(pat)
        while i >= 0:
            a = sa + i
            (aligned if (a & 7) == 0 else unaligned).append(a)
            i = blob.find(pat, i + 1)
    return aligned, unaligned


def main():
    p = sys.argv[1]
    md = MD(p)
    for s in sys.argv[2:]:
        val = int(s, 16)
        al, un = hunt(md, val)
        print("value 0x%X : %d 8-aligned slot(s), %d unaligned" % (val, len(al), len(un)))
        for a in al[:60]:
            print("    slot 0x%X   [%s]" % (a, classify(md, a)))
        if len(al) > 60:
            print("    ... %d more" % (len(al) - 60))
        print("")


if __name__ == '__main__':
    main()
