#!/usr/bin/env python3
# LANE 3 (b)/(d) -- prove that dumpimage's OWN manifests already record the hidden
# protector mapping's executable regions, and that dumpimage skipped every one.
#
# The protector image (SizeOfImage 0x4066000) has exactly four executable sub-regions,
# measured from crashpad MemoryInfoList:
#     +0x7000    0x1000
#     +0x7CF000  0x170000
#     +0x127C000 0x22E000
#     +0x1520000 0x2A49000       -> 48,136,192 exec bytes per mapping
# Look for that offset signature in each .dump.txt's Image-type rows.
#
# Usage: python protector_in_manifests.py <dumps-root>

import os, re, sys, collections

SIG = [(0x7000, 0x1000), (0x7CF000, 0x170000), (0x127C000, 0x22E000), (0x1520000, 0x2A49000)]
HDR = re.compile(r'^0x([0-9A-F]+)\s+0x([0-9A-F]+)\s+0x([0-9A-F]+)\s+(\S+)\s+(.*)$')


def rows_of(path):
    out = []
    inrows = False
    for line in open(path, 'r', encoding='utf-8', errors='replace'):
        s = line.strip()
        if s.startswith('VA ') and 'SIZE' in s:
            inrows = True
            continue
        if inrows:
            m = HDR.match(s)
            if m:
                out.append((int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16),
                            m.group(4), m.group(5)))
            elif s.startswith('('):
                inrows = False
    return out


def main():
    root = sys.argv[1]
    nfound = 0
    ndumps = 0
    print('%-30s %-18s %-10s %s' % ('DUMP DIR', 'PROTECTOR BASE', 'EXECBYTES', 'DUMPED?'))
    for d in sorted(os.listdir(root)):
        mf = os.path.join(root, d, 'SUPERVIVE-Win64-Shipping.dump.txt')
        if not os.path.exists(mf):
            continue
        ndumps += 1
        rows = rows_of(mf)
        bysz = collections.defaultdict(list)
        for va, sz, prot, typ, dumped in rows:
            if typ == 'Image':
                bysz[sz].append((va, prot, dumped))
        # a candidate base is any va of the 0x2A49000 row minus 0x1520000
        cands = []
        for va, prot, dumped in bysz.get(0x2A49000, []):
            cands.append(va - 0x1520000)
        for b in sorted(set(cands)):
            hits = 0
            execbytes = 0
            dumpedstr = set()
            for off, sz in SIG:
                for va, prot, dumped in bysz.get(sz, []):
                    if va == b + off:
                        hits += 1
                        execbytes += sz
                        dumpedstr.add(dumped.strip())
            if hits >= 3:
                nfound += 1
                print('%-30s 0x%-16X %-10d %s' % (d, b, execbytes, ' | '.join(sorted(dumpedstr))[:60]))
    print('')
    print('manifests scanned: %d   protector mappings identified in them: %d' % (ndumps, nfound))


if __name__ == '__main__':
    main()
