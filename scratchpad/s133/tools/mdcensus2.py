#!/usr/bin/env python3
# LANE 3 (a) supplement -- for a SAMPLE of minidumps, break captured memory down by
# WHICH loaded module (if any) each captured range falls inside, plus the
# non-module remainder. This is the discriminating control for
# "the parser found no game-image bytes": if it finds bytes inside OTHER
# modules, the null is specific to the game image; if it finds bytes inside
# NO module at all, the null is a property of what crashpad captures.
#
# Usage: python mdcensus2.py <dmp> [<dmp> ...]

import os, struct, sys
from mdcensus import parse, read_at, read_mdstring, ST_MEMORY_LIST, ST_MEMORY64_LIST


def main():
    for p in sys.argv[1:]:
        r = parse(p)
        if not r['ok']:
            print('SKIP %s %s' % (p, r['err']))
            continue
        mods = r['modnames']
        # rebuild ranges
        ranges = []
        with open(p, 'rb') as f:
            hdr = read_at(f, 0, 32)
            sig, ver, nstreams, dirrva, csum, ts, flags = struct.unpack('<IIIIIIQ', hdr)
            d = read_at(f, dirrva, nstreams * 12)
            for i in range(nstreams):
                st, dsz, drva = struct.unpack_from('<III', d, i * 12)
                if st == ST_MEMORY_LIST:
                    blob = read_at(f, drva, dsz)
                    nr = struct.unpack_from('<I', blob, 0)[0]
                    for k in range(nr):
                        start, sz, rva = struct.unpack_from('<QII', blob, 4 + k * 16)
                        ranges.append((start, sz))
        permod = {}
        nomod = 0
        nomod_ranges = 0
        for start, sz in ranges:
            hit = None
            for base, ssize, name in mods:
                if start < base + ssize and start + sz > base:
                    hit = name
                    break
            if hit:
                permod[hit] = permod.get(hit, 0) + sz
            else:
                nomod += sz
                nomod_ranges += 1
        print('=== %s ===' % p)
        print('  file=%d captured=%d ranges=%d threads=%d modules=%d meminfo_entries=%d'
              % (r['size'], r['bytes_captured'], r['n_ranges'], r['nthreads'],
                 r['nmodules'], r['n_meminfo']))
        print('  game image base=0x%X size=0x%X' % (r['game_base'], r['game_size']))
        print('  bytes inside ANY loaded module : %d across %d module(s)'
              % (sum(permod.values()), len(permod)))
        for name, b in sorted(permod.items(), key=lambda kv: -kv[1])[:15]:
            print('     %-70s %d' % (os.path.basename(name), b))
        print('  bytes inside NO module         : %d in %d ranges' % (nomod, nomod_ranges))
        # size histogram of ranges
        big = sorted(ranges, key=lambda t: -t[1])[:6]
        print('  largest ranges: ' + ', '.join('0x%X@0x%X' % (s, a) for a, s in big))


if __name__ == '__main__':
    main()
