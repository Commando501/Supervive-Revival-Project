#!/usr/bin/env python3
# LANE 3 (c) -- detail the HIDDEN MEM_IMAGE allocations found by hidden_image_census.py.
# For a chosen dump, print the full region map (BaseAddress, RegionSize, State,
# Protect) of each hidden allocation. This is the protector's own section layout,
# recovered offline from a crashpad minidump.
#
# Also: group every dump by which high (ASLR) runtime base it carries, and print the
# dump's crash timestamp, so "constant per boot" can be checked over 394 files
# instead of 31.
#
# Usage: python protector_map.py map <dmp> <allocbase-hex>
#        python protector_map.py groups <root>

import os, struct, sys, collections, datetime
from mdcensus import parse, read_at
from hidden_image_census import meminfo, MEM_IMAGE, PROTNAME

STATE = {0x1000: 'COMMIT', 0x2000: 'RESERVE', 0x10000: 'FREE'}
TYPE = {0x1000000: 'IMAGE', 0x40000: 'MAPPED', 0x20000: 'PRIVATE'}


def cmd_map(dmp, allocbase):
    mi = meminfo(dmp)
    rows = [m for m in mi if m[1] == allocbase]
    rows.sort()
    print('=== %s ===' % dmp)
    print('AllocationBase 0x%X  regions=%d  total=%d bytes' %
          (allocbase, len(rows), sum(m[3] for m in rows)))
    print('%-18s %-12s %-8s %-18s %-8s' % ('BASE', 'SIZE', 'STATE', 'PROTECT', 'TYPE'))
    for baseaddr, ab, allocprot, regsize, state, prot, typ in rows:
        print('0x%-16X 0x%-10X %-8s %-18s %-8s  (+0x%X)' %
              (baseaddr, regsize, STATE.get(state, hex(state)),
               PROTNAME.get(prot, hex(prot)), TYPE.get(typ, hex(typ)), baseaddr - allocbase))
    ex = sum(m[3] for m in rows if m[5] in (0x10, 0x20, 0x40, 0x80))
    print('executable bytes in this allocation: %d' % ex)


def timestamp_of(dmp):
    with open(dmp, 'rb') as f:
        hdr = read_at(f, 0, 32)
        sig, ver, ns, dr, cs, ts, fl = struct.unpack('<IIIIIIQ', hdr)
    return ts


def cmd_groups(root):
    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    groups = collections.defaultdict(list)
    lowcount = 0
    gamecopy = collections.Counter()
    nfiles = 0
    for p in files:
        r = parse(p)
        if not r['ok']:
            continue
        nfiles += 1
        mi = meminfo(p)
        modbases = set(b for b, s, n in r['modnames'])
        img = collections.defaultdict(int)
        for baseaddr, allocbase, allocprot, regsize, state, prot, typ in mi:
            if typ == MEM_IMAGE:
                img[allocbase] += regsize
        unknown = {b: sz for b, sz in img.items() if b not in modbases}
        high = [b for b, sz in unknown.items() if sz == 0x4066000 and b > 0x10000000000]
        low = [b for b, sz in unknown.items() if sz == 0x4066000 and b < 0x10000000000]
        gamesz = [b for b, sz in unknown.items() if sz == 0xA9E1000]
        if low:
            lowcount += 1
        for b in gamesz:
            gamecopy[len(gamesz)] += 1
        ts = timestamp_of(p)
        key = tuple(sorted(high))
        groups[key].append((ts, p, tuple(sorted(low)), tuple(sorted(gamesz))))
    print('dumps parsed: %d' % nfiles)
    print('dumps carrying a LOW (non-ASLR) 0x4066000 MEM_IMAGE alloc: %d' % lowcount)
    print('')
    print('=== grouping by HIGH 0x4066000 hidden MEM_IMAGE base (candidate runtime.dll) ===')
    for key, lst in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lst.sort()
        t0 = datetime.datetime.utcfromtimestamp(lst[0][0]).isoformat()
        t1 = datetime.datetime.utcfromtimestamp(lst[-1][0]).isoformat()
        lows = collections.Counter(x[2] for x in lst)
        print('base=%s  n=%d  first=%sZ  last=%sZ' %
              (','.join('0x%X' % b for b in key) or '(none)', len(lst), t0, t1))
        for lo, n in lows.items():
            print('    low alloc %s : %d dumps' % (','.join('0x%X' % b for b in lo) or '(none)', n))
    print('')
    print('=== hidden MEM_IMAGE allocations of exactly 0xA9E1000 (= game SizeOfImage) ===')
    for k, v in sorted(gamecopy.items()):
        print('  dumps with %d such allocation(s): %d' % (k, v))


if __name__ == '__main__':
    if sys.argv[1] == 'map':
        cmd_map(sys.argv[2], int(sys.argv[3], 16))
    else:
        cmd_groups(sys.argv[2])
