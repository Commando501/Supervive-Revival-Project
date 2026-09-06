#!/usr/bin/env python
"""q1b_dualmap.py -- FOLLOW-UP TO Q1, unplanned: the corpus-wide 0x4066000-span scan found
TWO hidden MEM_IMAGE allocations of that span, not one.

  (a) the per-boot high address that IS the kill target      (15 regions)
  (b) a FIXED low address 0xFF760000, present in 123/124 reports, in EVERY boot session
      (10 regions)  -- never recorded anywhere in the project

Both are MEM_IMAGE with the same SizeOfImage span and neither is in the ModuleList.
This tool prints the full region layout of both, aligns them by offset-from-AllocationBase,
and tests whether they are two views of ONE image.

POSITIVE CONTROL: the same offset-alignment is run on ntdll.dll -- a real image with a
known-good section layout -- and its region offsets must line up with its PE section
headers, which are readable from the on-disk ntdll (not done here) or at minimum must be
page-aligned and monotone.  The discriminating control used instead is: (a) and (b) must
agree offset-for-offset AND size-for-size if they are the same image; a coincidence of
total span alone would not.

usage: python q1b_dualmap.py [dump.dmp ...]
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump, STATE, TYPE, protname            # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402

SPAN = 0x4066000


def layout(mi, ab):
    g = sorted([x for x in mi if x[1] == ab], key=lambda x: x[0])
    return [(x[0] - ab, x[3], protname(x[5]), protname(x[2]), STATE.get(x[4], hex(x[4])),
             TYPE.get(x[6], hex(x[6]))) for x in g]


def show(path):
    d = Dump(path)
    mi = fast_meminfo(path, d.streams)
    groups = collections.defaultdict(list)
    for x in mi:
        if x[6] == 0x1000000:
            groups[x[1]].append(x)
    hits = sorted(ab for ab, g in groups.items() if sum(y[3] for y in g) == SPAN)
    print("dump: %s" % path)
    print("  MEM_IMAGE allocations with span 0x%X : %s" % (SPAN, [hex(h) for h in hits]))
    lays = {}
    for ab in hits:
        L = layout(mi, ab)
        lays[ab] = L
        print("\n  AllocationBase 0x%X   regions=%d   in_modlist=%s" %
              (ab, len(L), bool(d.modof(ab))))
        for off, sz, pr, ap, st, ty in L:
            print("     +0x%08X  size 0x%08X  prot=%-16s aprot=%-18s %s/%s"
                  % (off, sz, pr, ap, st, ty))
    if len(hits) == 2:
        a, b = hits
        # merge adjacent same-prot runs to compare structure at PAGE-BOUNDARY level
        def edges(L):
            e = []
            for off, sz, *_ in L:
                e.append(off)
            e.append(SPAN)
            return e
        ea, eb = edges(lays[a]), edges(lays[b])
        print("\n  boundary offsets (low  0x%X): %s" % (a, [hex(x) for x in ea]))
        print("  boundary offsets (high 0x%X): %s" % (b, [hex(x) for x in eb]))
        common = sorted(set(ea) & set(eb))
        print("  shared boundary offsets: %d of %d(low)/%d(high)  -> %s"
              % (len(common), len(ea), len(eb), [hex(x) for x in common]))
        # exec-region comparison
        xa = [(o, s) for o, s, pr, *_ in lays[a] if 'EXECUTE' in pr]
        xb = [(o, s) for o, s, pr, *_ in lays[b] if 'EXECUTE' in pr]
        print("  EXECUTE regions low : %s" % [(hex(o), hex(s)) for o, s in xa])
        print("  EXECUTE regions high: %s" % [(hex(o), hex(s)) for o, s in xb])
        print("  EXECUTE offset+size sets identical? %s" % (set(xa) == set(xb)))

    # POSITIVE CONTROL: ntdll's own region layout, a known real image
    nb = d.modbase('ntdll.dll')
    if nb:
        L = layout(mi, nb)
        print("\n  [CONTROL] ntdll.dll @0x%X regions=%d in_modlist=%s span=0x%X"
              % (nb, len(L), bool(d.modof(nb)), sum(x[1] for x in L)))
        for off, sz, pr, ap, st, ty in L:
            print("     +0x%08X  size 0x%08X  prot=%-16s aprot=%-18s %s/%s"
                  % (off, sz, pr, ap, st, ty))


if __name__ == '__main__':
    paths = sys.argv[1:]
    if not paths:
        rows = list(csv.DictReader(
            open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'), delimiter='\t'))
        # one representative per boot session
        seen = {}
        for r in rows:
            if r['ntdll'] not in seen and r['killalloc_base']:
                seen[r['ntdll']] = r['first_path']
        paths = list(seen.values())
    for p in paths:
        show(p)
        print("\n" + "=" * 96 + "\n")
