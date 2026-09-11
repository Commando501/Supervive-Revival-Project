#!/usr/bin/env python3
# LANE 3 (c) -- the hidden MEM_IMAGE allocation of exactly 0xA9E1000 bytes
# (== SUPERVIVE-Win64-Shipping SizeOfImage) present in 394/394 minidumps:
#   * where is it, is it stable, how many regions does it have
#   * did crashpad capture ANY bytes of it?  (if yes -> free plaintext/ciphertext sample)
#   * which dumps lack the low 0xFF760000 protector mapping
#
# Usage: python gamecopy_probe.py <root>

import os, struct, sys, collections
from mdcensus import parse, read_at, ST_MEMORY_LIST
from hidden_image_census import meminfo, MEM_IMAGE, PROTNAME

GAME_SOI = 0xA9E1000
RT_SOI = 0x4066000


def ranges_of(p):
    out = []
    with open(p, 'rb') as f:
        hdr = read_at(f, 0, 32)
        sig, ver, ns, dr, cs, ts, fl = struct.unpack('<IIIIIIQ', hdr)
        d = read_at(f, dr, ns * 12)
        for i in range(ns):
            st, dsz, drva = struct.unpack_from('<III', d, i * 12)
            if st == ST_MEMORY_LIST:
                blob = read_at(f, drva, dsz)
                nr = struct.unpack_from('<I', blob, 0)[0]
                for k in range(nr):
                    start, sz, rva = struct.unpack_from('<QII', blob, 4 + k * 16)
                    out.append((start, sz, rva))
    return out


def main():
    root = sys.argv[1]
    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    bases = collections.Counter()
    nregions = collections.Counter()
    prots = collections.Counter()
    captured = 0
    nolow = []
    n = 0
    for p in files:
        r = parse(p)
        if not r['ok']:
            continue
        n += 1
        mi = meminfo(p)
        modbases = set(b for b, s, nm in r['modnames'])
        img = collections.defaultdict(int)
        cnt = collections.Counter()
        pr = collections.defaultdict(set)
        for baseaddr, allocbase, allocprot, regsize, state, prot, typ in mi:
            if typ == MEM_IMAGE:
                img[allocbase] += regsize
                cnt[allocbase] += 1
                pr[allocbase].add(prot)
        unknown = {b: sz for b, sz in img.items() if b not in modbases}
        low = [b for b, sz in unknown.items() if sz == RT_SOI and b < 0x10000000000]
        if not low:
            nolow.append(p)
        gc = [b for b, sz in unknown.items() if sz == GAME_SOI]
        for b in gc:
            bases[b] += 1
            nregions[cnt[b]] += 1
            for x in pr[b]:
                prots[PROTNAME.get(x, hex(x))] += 1
            lo, hi = b, b + GAME_SOI
            for start, sz, rva in ranges_of(p):
                if start < hi and start + sz > lo:
                    captured += min(start + sz, hi) - max(start, lo)
    print('dumps parsed: %d' % n)
    print('distinct base addresses of the hidden 0xA9E1000 MEM_IMAGE copy: %d' % len(bases))
    print('region-count histogram for it: %s' % dict(nregions))
    print('protections seen on it       : %s' % dict(prots))
    print('BYTES OF IT CAPTURED BY CRASHPAD (all dumps): %d' % captured)
    print('')
    print('dumps WITHOUT the low 0xFF760000-class protector mapping: %d' % len(nolow))
    for p in nolow:
        print('   ' + p)
    print('')
    print('top 10 base addresses:')
    for b, c in bases.most_common(10):
        print('   0x%-14X %d dumps' % (b, c))


if __name__ == '__main__':
    main()
