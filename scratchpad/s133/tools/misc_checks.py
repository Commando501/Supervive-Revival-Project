#!/usr/bin/env python3
# LANE 3 -- odds and ends:
#  1. what MEM_ type/protection the GAME image itself carries at death
#     (repo claims MEM_MAPPED, never verified offline)
#  2. the unknown minidump stream 0x434C1001 -- size and first bytes
#  3. minidump header Flags (which MINIDUMP_TYPE crashpad asked for)
#
# Usage: python misc_checks.py <dmp> [<dmp> ...]

import os, struct, sys, collections
from mdcensus import parse, read_at
from hidden_image_census import meminfo, PROTNAME

TYPE = {0x1000000: 'IMAGE', 0x40000: 'MAPPED', 0x20000: 'PRIVATE', 0: 'none'}
STATE = {0x1000: 'COMMIT', 0x2000: 'RESERVE', 0x10000: 'FREE'}


def main():
    for p in sys.argv[1:]:
        r = parse(p)
        if not r['ok']:
            continue
        with open(p, 'rb') as f:
            hdr = read_at(f, 0, 32)
            sig, ver, ns, dr, cs, ts, flags = struct.unpack('<IIIIIIQ', hdr)
            d = read_at(f, dr, ns * 12)
            unk = []
            for i in range(ns):
                st, dsz, drva = struct.unpack_from('<III', d, i * 12)
                if st > 0x10000:
                    unk.append((st, dsz, read_at(f, drva, min(dsz, 64))))
        gb, gs = r['game_base'], r['game_size']
        mi = meminfo(p)
        cnt = collections.Counter()
        alloc = collections.Counter()
        for baseaddr, allocbase, allocprot, regsize, state, prot, typ in mi:
            if gb <= baseaddr < gb + gs:
                cnt[(TYPE.get(typ, hex(typ)), STATE.get(state, hex(state)),
                     PROTNAME.get(prot, hex(prot)))] += regsize
                alloc[allocbase] += 1
        print('=== %s ===' % p)
        print('  header Flags = 0x%X   streams=%d' % (flags, ns))
        print('  game image 0x%X..0x%X region breakdown (bytes):' % (gb, gb + gs))
        for k, v in cnt.most_common():
            print('     %-8s %-8s %-18s %12d' % (k[0], k[1], k[2], v))
        print('  distinct AllocationBases covering the game image: %s'
              % ', '.join('0x%X(x%d)' % (b, n) for b, n in alloc.most_common(4)))
        for st, dsz, head in unk:
            print('  stream 0x%X size=%d head=%s' % (st, dsz, head[:32].hex()))


if __name__ == '__main__':
    main()
