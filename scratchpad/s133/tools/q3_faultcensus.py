#!/usr/bin/env python
"""q3_faultcensus.py -- Q3: full fault census + reconciliation with the counts recorded in
CLAUDE.md / scratchpad/s131/evidence/FK31-kill-address-is-constant.md.

CLAIM UNDER TEST (S131, quoted): "Filter, applied to every dumps/crashpad-*/reports/*.dmp
on disk: 0xC0000005, ExceptionInformation[0]==8, addr & 0xFFF == 1.  31 minidumps match
(unit: minidump files)... 0x7FFD3B400001 13 / 0x7FFA42600001 11 / 0x7FFB57400001 7."

This reproduces that filter at BOTH units -- FILES (S131's stated unit) and DISTINCT
CRASHPAD REPORTS (dedup by report GUID) -- and quantifies the DEATH/untagged pairing that
S131 flagged but did not measure.

POSITIVE CONTROL for the file->report dedup: two files with the same report GUID must be
byte-identical.  Verified separately (all 118 multi-copy groups: 1 distinct sha256 each,
except f053db6e where one copy is a 6,460,608 B truncation of the 41,131,872 B complete
report -- handled by taking the largest).

usage: python q3_faultcensus.py
"""
import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402

FILES = sorted(glob.glob('dumps/crashpad-*/reports/*.dmp'))
print("=" * 100)
print("Q3  FAULT CENSUS")
print("=" * 100)
print("minidump FILES on disk under dumps/crashpad-*/reports/ : %d" % len(FILES))

recs = []
fail = []
for p in FILES:
    d = Dump(p)
    if not d.ok:
        fail.append((p, d.err))
        continue
    e = d.exc
    recs.append(dict(path=p.replace('\\', '/'),
                     guid=os.path.basename(p),
                     dirname=p.replace('\\', '/').split('/')[1],
                     size=os.path.getsize(p),
                     code=e['code'] if e else None,
                     addr=e['addr'] if e else None,
                     p0=(e['parms'][0] if e and e['parms'] else None),
                     rip=d.rip,
                     ntdll=d.modbase('ntdll.dll'),
                     ctime=(d.misc or {}).get('create_time', 0),
                     ripmod=d.modof(d.rip) if d.rip else None))
print("parsed OK: %d   parse failures: %d %s" % (len(recs), len(fail), fail[:3]))

print("\n--- exception CODE census (unit: files) ---")
for c, n in collections.Counter(r['code'] for r in recs).most_common():
    print("   0x%08X  %d" % (c, n))

print("\n--- ExceptionInformation[0] census for 0xC0000005 (unit: files) ---")
ACC = {0: 'READ', 1: 'WRITE', 8: 'EXECUTE'}
for c, n in collections.Counter(r['p0'] for r in recs if r['code'] == 0xC0000005).most_common():
    print("   %s (%s)  %d" % (c, ACC.get(c, '?'), n))


def fam(r):
    return (r['code'] == 0xC0000005 and r['p0'] == 8 and r['addr'] is not None
            and (r['addr'] & 0xFFF) == 1)


F = [r for r in recs if fam(r)]
print("\n" + "=" * 100)
print("THE S131 FILTER {0xC0000005, ExcInfo[0]==8, addr&0xFFF==1}")
print("=" * 100)
print("MATCHING FILES                : %d      (S131 recorded 31)" % len(F))
guids = set(r['guid'] for r in F)
print("MATCHING DISTINCT REPORTS     : %d" % len(guids))
print("\nby faulting address (unit: FILES  |  unit: DISTINCT REPORTS):")
byaddr_f = collections.Counter(r['addr'] for r in F)
byaddr_g = collections.Counter()
seen = set()
for r in F:
    if r['guid'] not in seen:
        seen.add(r['guid'])
        byaddr_g[r['addr']] += 1
for a, n in sorted(byaddr_f.items()):
    ds = sorted(set(r['dirname'][9:17] for r in F if r['addr'] == a))
    print("   0x%016X   files=%-4d reports=%-4d   archive-dir dates %s .. %s"
          % (a, n, byaddr_g[a], ds[0], ds[-1]))
print("\nS131 recorded: 0x7FFD3B400001 13 / 0x7FFA42600001 11 / 0x7FFB57400001 7  (files)")

# ---- the DEATH/untagged pairing, measured ----
print("\n" + "=" * 100)
print("FILES-vs-CRASHES: quantifying the archiver's -DEATH / untagged duplication")
print("=" * 100)
bg = collections.defaultdict(list)
for r in recs:
    bg[r['guid']].append(r)
copies = collections.Counter(len(v) for v in bg.values())
print("distinct report GUIDs: %d   from %d files" % (len(bg), len(recs)))
print("copies-per-GUID histogram (unit: GUIDs):", dict(sorted(copies.items())))
print("mean files per distinct report: %.3f" % (len(recs) / len(bg)))
lab = collections.Counter()
for g, v in bg.items():
    tags = ['DEATH' if 'DEATH' in r['dirname'] else 'plain' for r in v]
    lab['+'.join(sorted(set(tags))) + ' x%d' % len(v)] += 1
print("\nper-GUID archive-dir tag pattern (unit: GUIDs):")
for k, n in lab.most_common():
    print("   %-20s %d" % (k, n))
print("\n=> S131's 'roughly half' is measured at %.3f files per distinct crash." %
      (len(recs) / len(bg)))

# ---- the non-family 0xC0000005s ----
print("\n" + "=" * 100)
print("NON-FAMILY 0xC0000005 reports (unit: distinct reports)")
print("=" * 100)
nf = {}
for r in recs:
    if r['code'] == 0xC0000005 and not fam(r):
        nf.setdefault(r['guid'], r)
low = collections.Counter(r['addr'] & 0xFFFF for r in nf.values())
print("distinct reports: %d" % len(nf))
print("addr & 0xFFFF histogram:", {hex(k): v for k, v in low.most_common()})
for g, r in sorted(nf.items(), key=lambda kv: kv[1]['ctime']):
    print("   %s  0x%012X  p0=%s  ntdll=0x%X  dir=%s"
          % (g[:8], r['addr'], ACC.get(r['p0'], r['p0']), r['ntdll'] or 0, r['dirname']))
