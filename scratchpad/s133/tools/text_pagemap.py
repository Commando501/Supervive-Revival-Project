#!/usr/bin/env python3
# LANE 3 (c)/(d) -- THE BIG ONE.
# Every crashpad minidump carries a MemoryInfoListStream = the full VirtualQueryEx
# region map at the instant of death. This build marks NEVER-DECRYPTED .text pages
# PAGE_NOACCESS and DECRYPTED ones PAGE_EXECUTE_READ (repo-measured, S121:
# 15,672 EXECUTE_READ + 14,609 NOACCESS = 30,281 = exactly the .text page count).
#
# => each minidump is a FREE, EXACT, PER-PAGE DECRYPTION MAP of .text at that death,
#    with ZERO captured bytes. Nobody has ever parsed it.
#
# We compute per dump:  decrypted .text pages, and the union across all dumps,
# then compare the union against what dumps/merged6.dump.exe actually holds.
# That bounds how much decrypted .text has EVER existed in a process we snapshotted.
#
# POSITIVE CONTROLS:
#   Q1 the .text region rows must tile [base+0x1000, +0x764A000) exactly (no gaps).
#   Q2 the two protection classes must sum to 30,281 pages.
#   Q3 .rdata (RVA 0x764A000, 9,085 pages) must be ~100% readable in every dump --
#      it is not demand-decrypted, so a parser that mislabels protections would
#      show .rdata dark too.
#
# Usage: python text_pagemap.py <root> [--csv out.csv] [--merged <merged.dump.exe>]

import os, struct, sys, csv, collections
from mdcensus import parse
from hidden_image_census import meminfo, PROTNAME

TEXT_RVA = 0x1000
TEXT_VSZ = 0x7649000
RDATA_RVA = 0x764A000
RDATA_VSZ = 0x237D000
PAGE = 0x1000
NTEXT = TEXT_VSZ // PAGE          # 30281
NRDATA = RDATA_VSZ // PAGE        # 9085
NOACCESS = 0x01
MEM_COMMIT = 0x1000


def pagemap(path):
    """returns (dict rva_page -> protect for .text, rdata_readable_pages, tiled_ok)"""
    r = parse(path)
    if not r['ok'] or not r['game_base']:
        return None
    gb = r['game_base']
    mi = meminfo(path)
    tstart, tend = gb + TEXT_RVA, gb + TEXT_RVA + TEXT_VSZ
    rstart, rend = gb + RDATA_RVA, gb + RDATA_RVA + RDATA_VSZ
    prot = {}
    rd_ok = 0
    covered = 0
    for baseaddr, allocbase, allocprot, regsize, state, p, typ in mi:
        lo, hi = baseaddr, baseaddr + regsize
        if hi > tstart and lo < tend:
            a = max(lo, tstart)
            b = min(hi, tend)
            covered += b - a
            for pg in range((a - tstart) // PAGE, (b - tstart) // PAGE):
                prot[pg] = p
        if hi > rstart and lo < rend:
            a = max(lo, rstart)
            b = min(hi, rend)
            if state == MEM_COMMIT and p != NOACCESS:
                rd_ok += (b - a) // PAGE
    return prot, rd_ok, covered, gb, r


def main():
    root = sys.argv[1]
    outcsv = None
    if '--csv' in sys.argv:
        outcsv = sys.argv[sys.argv.index('--csv') + 1]
    merged = None
    if '--merged' in sys.argv:
        merged = sys.argv[sys.argv.index('--merged') + 1]

    files = []
    for dp, dn, fn in os.walk(root):
        for n in fn:
            if n.lower().endswith('.dmp'):
                files.append(os.path.join(dp, n))
    files.sort()

    union = set()
    rows = []
    q1 = q2 = q3 = 0
    n = 0
    protkinds = collections.Counter()
    byguid = {}
    for p in files:
        res = pagemap(p)
        if res is None:
            continue
        prot, rd_ok, covered, gb, r = res
        n += 1
        dec = set(pg for pg, pv in prot.items() if pv != NOACCESS)
        for pv in prot.values():
            protkinds[pv] += 1
        if covered == TEXT_VSZ:
            q1 += 1
        if len(prot) == NTEXT:
            q2 += 1
        if rd_ok >= NRDATA * 0.99:
            q3 += 1
        union |= dec
        guid = os.path.basename(p)
        # keep the max-coverage instance per distinct crash GUID
        if guid not in byguid or len(dec) > byguid[guid][0]:
            byguid[guid] = (len(dec), p)
        rows.append((p, guid, hex(gb), len(prot), len(dec), rd_ok))
    print('=== .text PAGE-PROTECTION MAP mined from crashpad MemoryInfoList ===')
    print('dumps parsed                       : %d' % n)
    print('distinct crash GUIDs               : %d' % len(byguid))
    print('CONTROL Q1 .text rows tile exactly : %d/%d' % (q1, n))
    print('CONTROL Q2 .text page count==30281 : %d/%d' % (q2, n))
    print('CONTROL Q3 .rdata >=99%% readable    : %d/%d' % (q3, n))
    print('protection values seen over .text  : %s'
          % ', '.join('%s=%d' % (PROTNAME.get(k, hex(k)), v) for k, v in protkinds.most_common()))
    print('')
    dec_counts = sorted(v[0] for v in byguid.values())
    print('decrypted .text pages per DISTINCT crash: min=%d median=%d max=%d'
          % (dec_counts[0], dec_counts[len(dec_counts) // 2], dec_counts[-1]))
    print('UNION of decrypted .text pages across ALL dumps : %d / %d (%.2f%%)'
          % (len(union), NTEXT, 100.0 * len(union) / NTEXT))
    print('')
    print('top 12 distinct crashes by decrypted .text pages:')
    for c, p in sorted(byguid.values(), reverse=True)[:12]:
        print('   %6d  %s' % (c, p))

    if merged:
        with open(merged, 'rb') as f:
            f.seek(TEXT_RVA)
            blob = f.read(TEXT_VSZ)
        mset = set()
        for pg in range(NTEXT):
            chunk = blob[pg * PAGE:(pg + 1) * PAGE]
            if any(chunk):
                mset.add(pg)
        print('')
        print('=== comparison with %s ===' % merged)
        print('merged non-zero .text pages        : %d' % len(mset))
        print('minidump-union decrypted pages     : %d' % len(union))
        print('in union but NOT in merged         : %d' % len(union - mset))
        print('in merged but NOT in union         : %d' % len(mset - union))
        print('union U merged                     : %d (%.2f%%)'
              % (len(union | mset), 100.0 * len(union | mset) / NTEXT))
        gain = sorted(union - mset)
        if gain:
            print('first 20 pages present at a crash but zero in merged (RVA):')
            print('   ' + ', '.join('0x%X' % (TEXT_RVA + g * PAGE) for g in gain[:20]))

    if outcsv:
        with open(outcsv, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['path', 'guid', 'game_base', 'text_pages_mapped',
                        'text_pages_decrypted', 'rdata_pages_readable'])
            for r in rows:
                w.writerow(r)
        print('')
        print('csv -> ' + outcsv)


if __name__ == '__main__':
    main()
