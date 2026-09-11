#!/usr/bin/env python
"""q1c_hidden_images.py -- census of EVERY MEM_IMAGE allocation in the process that is NOT
in the minidump ModuleList (i.e. every manually-mapped / PEB-unlinked image), across the
whole crashpad corpus.

Motivation: the Q1 scan for span==0x4066000 turned up TWO hidden runtime.dll mappings, one
of which nothing in this project had ever recorded.  A general census asks: how many hidden
images are there, how big, and are any of them stable enough to be levers?

POSITIVE CONTROL: 219 of the 220 ModuleList entries must come back "visible" -- if the
visible/hidden classifier cannot recognise ordinary loaded DLLs it is not measuring
hiddenness.  The count of MEM_IMAGE allocations that ARE in the module list is printed
beside the hidden count for exactly that reason.

usage: python q1c_hidden_images.py [sweep.tsv]
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump, protname                          # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402

TSV = sys.argv[1] if len(sys.argv) > 1 else 'scratchpad/s133/evidence/md_sweep.tsv'
rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))

print("=" * 104)
print("Q1c  HIDDEN-IMAGE CENSUS (MEM_IMAGE allocations absent from ModuleList)")
print("     unit: distinct crashpad reports (%d)" % len(rows))
print("=" * 104)

hidden_hist = collections.Counter()      # (span, nregions) -> reports
hidden_bases = collections.Counter()     # base -> reports
per_report = []
vis_tot = hid_tot = 0
for r in rows:
    d = Dump(r['first_path'])
    if not d.ok:
        continue
    mi = fast_meminfo(r['first_path'], d.streams)
    groups = collections.defaultdict(list)
    for x in mi:
        if x[6] == 0x1000000:            # MEM_IMAGE
            groups[x[1]].append(x)
    vis = hid = 0
    hb = []
    for ab, g in groups.items():
        span = sum(y[3] for y in g)
        if d.modof(ab):
            vis += 1
        else:
            hid += 1
            hb.append((ab, span, len(g)))
            hidden_hist[(span, len(g))] += 1
            hidden_bases[ab] += 1
    vis_tot += vis
    hid_tot += hid
    per_report.append((r, vis, hid, sorted(hb)))

print("\nCONTROL  MEM_IMAGE allocations that ARE in the ModuleList: %d over %d reports"
      "  (mean %.1f/report; ModuleList has %s entries/report)"
      % (vis_tot, len(per_report), vis_tot / max(1, len(per_report)), rows[0]['nmods']))
print("         MEM_IMAGE allocations that are NOT: %d over %d reports (mean %.2f/report)"
      % (hid_tot, len(per_report), hid_tot / max(1, len(per_report))))

print("\n--- hidden-image SHAPES (span, region-count) -> reports ---")
for (span, nreg), n in hidden_hist.most_common(20):
    print("   span 0x%-10X regions %-3d   seen in %d reports" % (span, nreg, n))

print("\n--- hidden-image BASES -> reports (top 20) ---")
for b, n in hidden_bases.most_common(20):
    print("   0x%-16X  %d reports" % (b, n))

print("\n--- per boot session: which hidden bases, and are they stable? ---")
byboot = collections.defaultdict(list)
for r, vis, hid, hb in per_report:
    byboot[r['ntdll']].append((r, hb))
for nb, lst in byboot.items():
    print("\n  boot ntdll=%s  reports=%d" % (nb, len(lst)))
    c = collections.Counter()
    for r, hb in lst:
        for ab, span, nreg in hb:
            c[(ab, span)] += 1
    for (ab, span), n in c.most_common():
        print("     0x%-16X span 0x%-10X  in %d/%d reports" % (ab, span, n, len(lst)))

print("\n--- the report(s) MISSING the fixed 0xFF760000 mapping ---")
for r, vis, hid, hb in per_report:
    if not any(ab == 0xFF760000 for ab, _s, _n in hb):
        print("   %s  %s  ntdll=%s  addr=%s  hidden=%s"
              % (r['create_iso'], r['guid'][:8], r['ntdll'], r['exc_addr'],
                 [(hex(a), hex(s)) for a, s, _ in hb]))
