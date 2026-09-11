#!/usr/bin/env python
"""q1_killregion.py -- Q1: does the FK-31 kill address land in a hidden MEM_IMAGE region,
and does the S131 LIVE VirtualQueryEx measurement reproduce OFFLINE across the corpus?

S131 measured, live, n=1 (scratchpad/s131/tools/fk31_map_kill_page.py):
    page  = MEM_COMMIT / PAGE_READONLY / MEM_IMAGE
    AllocationBase == the address itself
    SizeOfImage 0x4066000, 11 sections
    (Get-Process).Modules reports NO module at that base  ==> manually mapped, hidden

This re-tests all four of those, offline, from MemoryInfoList (stream 16) + ModuleList
(stream 4), on every dump in the corpus.

POSITIVE CONTROL (required, method rule 1): the same code path is run against a
KNOWN-VISIBLE module base -- ntdll.dll -- which MUST come back type=IMAGE,
in_modlist=1.  If the "hidden" test cannot see ntdll as visible, the test is broken and
its "hidden" verdict is worthless.

usage: python q1_killregion.py [sweep.tsv]
"""
import csv
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump, STATE, TYPE, protname            # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402

TSV = sys.argv[1] if len(sys.argv) > 1 else 'scratchpad/s133/evidence/md_sweep.tsv'
rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))

print("=" * 100)
print("Q1  KILL-REGION CENSUS  (unit: distinct crashpad reports, deduped by report GUID)")
print("=" * 100)
print("corpus: %d distinct reports" % len(rows))

# ---------- the FK-31 family filter, exactly as CLAUDE.md states it ----------
fam = [r for r in rows if r['exc_code'] == '0xC0000005'
       and r['exc_p0'] == '0x8'
       and r['exc_addr'] and int(r['exc_addr'], 16) & 0xFFF == 1]
print("FK-31 family {0xC0000005, ExceptionInformation[0]==8, addr&0xFFF==1}: %d reports"
      % len(fam))

addrs = collections.Counter(r['exc_addr'] for r in fam)
print("\ndistinct faulting addresses in family (unit: reports):")
for a, n in addrs.most_common():
    print("   %-18s  %d" % (a, n))

print("\n--- per-address region shape (all reports agree unless noted) ---")
for a in addrs:
    sub = [r for r in fam if r['exc_addr'] == a]
    keys = collections.Counter(
        (r['killreg_state'], r['killreg_type'], r['killreg_prot'], r['killreg_aprot'],
         r['killreg_size'], r['killalloc_base'], r['killalloc_nregions'],
         r['killalloc_span'], r['killalloc_exec_regions'], r['killalloc_in_modlist'])
        for r in sub)
    print("\n  %s   n=%d  distinct shapes=%d" % (a, len(sub), len(keys)))
    for k, n in keys.most_common():
        st, ty, pr, ap, sz, ab, nreg, span, nexe, inml = k
        print("     n=%-3d region: %s/%s prot=%s aprot=%s size=%s" % (n, st, ty, pr, ap, sz))
        print("           alloc : base=%s  regions=%s  span=%s  exec_regions=%s  in_modlist=%s"
              % (ab, nreg, span, nexe, inml))
        print("           AllocationBase == addr&~0xFFF ? %s"
              % ("YES" if ab and int(ab, 16) == (int(a, 16) & ~0xFFF) else "NO"))

# ---------- POSITIVE CONTROL ----------
print("\n" + "=" * 100)
print("POSITIVE CONTROL: run the identical region+modlist query against ntdll.dll's base")
print("  (a module that IS in the loader list).  Expect type=IMAGE, in_modlist=1.")
print("=" * 100)
ctl_ok = ctl_bad = 0
ctl_detail = collections.Counter()
sample = fam[:] or rows[:]
for r in sample:
    d = Dump(r['first_path'])
    if not d.ok:
        continue
    nb = d.modbase('ntdll.dll')
    if not nb:
        ctl_bad += 1
        continue
    mi = fast_meminfo(r['first_path'], d.streams)
    hit = None
    for (b, a2, ap, sz, st, pr, ty) in mi:
        if b <= nb < b + sz:
            hit = (b, a2, ap, sz, st, pr, ty)
            break
    if not hit:
        ctl_bad += 1
        continue
    b, a2, ap, sz, st, pr, ty = hit
    grp = [x for x in mi if x[1] == a2]
    span = sum(x[3] for x in grp)
    inml = 1 if d.modof(a2) else 0
    ctl_detail[(TYPE.get(ty, hex(ty)), STATE.get(st, hex(st)), protname(pr),
                inml, hex(span), len(grp))] += 1
    if TYPE.get(ty) == 'IMAGE' and inml == 1:
        ctl_ok += 1
    else:
        ctl_bad += 1
print("control PASS=%d  FAIL=%d   (unit: reports)" % (ctl_ok, ctl_bad))
for k, n in ctl_detail.most_common(6):
    print("   n=%-3d ntdll region: type=%s state=%s prot=%s in_modlist=%d span=%s regions=%d"
          % (n, k[0], k[1], k[2], k[3], k[4], k[5]))

# ---------- is the kill alloc base EVER in the module list? ----------
print("\n--- 'hidden from the module list' check across the family ---")
c = collections.Counter(r['killalloc_in_modlist'] for r in fam)
print("   killalloc_in_modlist counts:", dict(c))
c2 = collections.Counter(r['runtime_in_modlist'] for r in rows)
print("   runtime.dll present in ModuleList, whole corpus:", dict(c2))

# ---------- what else lives at that ALLOC base?  Any other MEM_IMAGE alloc of the
#            same 0x4066000 span anywhere in the corpus? ----------
print("\n--- corpus-wide: every MEM_IMAGE AllocationBase whose span == 0x4066000 ---")
spans = collections.Counter()
for r in rows[:len(rows)]:
    d = Dump(r['first_path'])
    if not d.ok:
        continue
    mi = fast_meminfo(r['first_path'], d.streams)
    groups = collections.defaultdict(list)
    for x in mi:
        if x[6] == 0x1000000:
            groups[x[1]].append(x)
    for ab, g in groups.items():
        sp = sum(y[3] for y in g)
        if sp == 0x4066000:
            spans[('0x%X' % ab, 1 if d.modof(ab) else 0, len(g))] += 1
for k, n in spans.most_common():
    print("   base=%-16s in_modlist=%d regions=%d   seen in %d reports" % (k[0], k[1], k[2], n))
