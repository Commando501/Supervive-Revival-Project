#!/usr/bin/env python3
# LANE 3 (a)/(b) -- hunt for MZ/PE headers inside minidump captured memory.
# Rationale: S131 measured that the protector's runtime.dll is MANUALLY MAPPED
# (MEM_IMAGE, hidden from the module list) with 'MZ' at its AllocationBase.
# If crashpad captured any range starting at such a base we get a free copy.
# Also reports whether the FK-31 constant kill addresses are covered.
#
# Usage: python mz_hunt.py <root>

import os, struct, sys
from mdcensus import parse, read_at, ST_MEMORY_LIST

KILL_ADDRS = [0x7FFD3B400001, 0x7FFA42600001, 0x7FFB57400001]


def main():
    root = sys.argv[1]
    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()
    nfiles = 0
    mz_hits = []
    kill_hits = []
    tot_ranges = 0
    for p in files:
        r = parse(p)
        if not r['ok']:
            continue
        nfiles += 1
        with open(p, 'rb') as f:
            hdr = read_at(f, 0, 32)
            sig, ver, nstreams, dirrva, csum, ts, flags = struct.unpack('<IIIIIIQ', hdr)
            d = read_at(f, dirrva, nstreams * 12)
            for i in range(nstreams):
                st, dsz, drva = struct.unpack_from('<III', d, i * 12)
                if st != ST_MEMORY_LIST:
                    continue
                blob = read_at(f, drva, dsz)
                nr = struct.unpack_from('<I', blob, 0)[0]
                for k in range(nr):
                    start, sz, rva = struct.unpack_from('<QII', blob, 4 + k * 16)
                    tot_ranges += 1
                    two = read_at(f, rva, 2)
                    if two == b'MZ':
                        mz_hits.append((p, start, sz, rva))
                    for ka in KILL_ADDRS:
                        if start <= ka < start + sz:
                            kill_hits.append((p, ka, start, sz, rva))
    print('=== MZ hunt in minidump captured memory ===')
    print('files parsed  : %d' % nfiles)
    print('ranges scanned: %d' % tot_ranges)
    print('ranges whose first 2 bytes are MZ: %d' % len(mz_hits))
    for p, start, sz, rva in mz_hits[:40]:
        print('   %s va=0x%X size=0x%X' % (p, start, sz))
    print('ranges covering an FK-31 constant kill address: %d' % len(kill_hits))
    for p, ka, start, sz, rva in kill_hits[:40]:
        print('   %s kill=0x%X in va=0x%X size=0x%X' % (p, ka, start, sz))


if __name__ == '__main__':
    main()
