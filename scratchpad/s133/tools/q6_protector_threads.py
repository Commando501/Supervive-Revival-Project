#!/usr/bin/env python
"""q6_protector_threads.py -- FK-10 Wall #7, from data already on disk.

q5b established [M] that the FK-31 kill faults on the FIRST instruction of a NEW thread
(bottom two frames = KERNEL32!BaseThreadInitThunk / ntdll!RtlUserThreadStart, nothing above,
rcx=0, rdi==rsp).  So the code that DECIDED to kill is NOT on the crashing stack -- it is on
whatever thread called NtCreateThreadEx, and that thread is still alive in the dump.

This scans EVERY captured thread stack in a dump for qwords that land inside the hidden
runtime.dll mapping, and reports the RVAs.  Those RVAs are return addresses into the
protector -- i.e. the call sites FK-10's Wall #7 has been hunting, expressed as
runtime.dll RVAs that can be fed straight to an offline disassembler (runtime.dll is NOT
packed: FK-10 [M]).

CONTROLS
  C1 the same scan counts qwords landing in KNOWN modules; a stack yielding zero of those
     was not captured, and its runtime.dll zero is uninterpretable.
  C2 the register census: rbp at the FK-31 fault.  If it is one constant corpus-wide it is a
     protector constant; if it varies it may encode which detector fired.
  C3 the 0x205d contrast family must NOT show the same runtime.dll RVA set, or the RVAs are
     ambient rather than kill-specific.

usage: python q6_protector_threads.py [--n N]
"""
import collections
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402
from q5_killstack import memranges                             # noqa: E402

N = 20
if '--n' in sys.argv:
    N = int(sys.argv[sys.argv.index('--n') + 1])

rows = list(csv.DictReader(open('scratchpad/s133/evidence/md_sweep.tsv', encoding='utf-8'),
                           delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))
fam = [r for r in rows if r['kill_shape'] == 'AV+EXEC+PLUS1']
ctr = [r for r in rows if r['exc_addr'] and int(r['exc_addr'], 16) & 0xFFFF == 0x205D]

print("=" * 100)
print("Q6  PROTECTOR RETURN ADDRESSES ON LIVE THREAD STACKS  (runtime.dll RVAs)")
print("=" * 100)

# ---- C2: register census over the whole FK-31 family ----
print("\nC2  register census at the FK-31 fault (unit: reports, n=%d)" % len(fam))
regstats = collections.defaultdict(collections.Counter)
for r in fam:
    d = Dump(r['first_path'])
    if not d.ok or not d.regs:
        continue
    for k in ('rax', 'rcx', 'rsi', 'rbp', 'rbx', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15'):
        regstats[k]['0x%X' % d.regs[k]] += 1
    regstats['rdi==rsp']['%s' % (d.regs['rdi'] == d.regs['rsp'])] += 1
for k in ('rax', 'rcx', 'rsi', 'rbp', 'rbx', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15',
          'rdi==rsp'):
    c = regstats[k]
    top = c.most_common(3)
    print("   %-9s distinct=%-4d  top: %s" % (k, len(c), top))


def scan(path, hidden_bases, label, quiet=False):
    d = Dump(path)
    rs = memranges(d)
    byaddr = sorted(rs)
    hits = collections.Counter()
    known = 0
    stacks = 0
    for t in d.threads:
        lo, sz = t['stack'], t['stacksize']
        if sz == 0:
            continue
        # find the captured bytes for this stack
        for sa, ssz, sr in rs:
            if not (sa < lo + sz and sa + ssz > lo):
                continue
            stacks += 1
            blob = d._at(sr, ssz)
            for i in range(0, len(blob) - 7, 8):
                q = struct.unpack_from('<Q', blob, i)[0]
                if q < 0x10000:
                    continue
                if d.modof(q):
                    known += 1
                    continue
                for ab, span in hidden_bases:
                    if ab <= q < ab + span:
                        hits[(ab, q - ab)] += 1
                        break
    if not quiet:
        print("  %s  stacks scanned=%d  C1 known-module qwords=%d  hidden-image qwords=%d"
              % (label, stacks, known, sum(hits.values())))
    return hits, known, stacks


print("\n--- scanning FK-31 reports (first %d) ---" % N)
agg = collections.Counter()
seen_reports = 0
for r in fam[:N]:
    d = Dump(r['first_path'])
    mi = fast_meminfo(r['first_path'], d.streams)
    groups = collections.defaultdict(int)
    for x in mi:
        if x[6] == 0x1000000:
            groups[x[1]] += x[3]
    hb = [(a, s) for a, s in groups.items() if not d.modof(a) and s == 0x4066000]
    hits, known, stacks = scan(r['first_path'], hb, "%s %s" % (r['create_iso'], r['guid'][:8]))
    seen_reports += 1
    for (ab, rva), n in hits.items():
        agg[rva] += 1        # count REPORTS-with-this-RVA, approximately (1 per occurrence)

print("\n--- aggregated runtime.dll RVAs seen on live thread stacks (top 40) ---")
print("    unit: total qword occurrences across %d FK-31 reports" % seen_reports)
for rva, n in agg.most_common(40):
    print("   runtime.dll+0x%08X   %d" % (rva, n))

print("\n--- C3 CONTRAST: same scan on the 0x205d family (our own DLL's fault) ---")
agg2 = collections.Counter()
for r in ctr[:5]:
    d = Dump(r['first_path'])
    mi = fast_meminfo(r['first_path'], d.streams)
    groups = collections.defaultdict(int)
    for x in mi:
        if x[6] == 0x1000000:
            groups[x[1]] += x[3]
    hb = [(a, s) for a, s in groups.items() if not d.modof(a) and s == 0x4066000]
    hits, known, stacks = scan(r['first_path'], hb, "%s %s" % (r['create_iso'], r['guid'][:8]))
    for (ab, rva), n in hits.items():
        agg2[rva] += 1
print("   distinct RVAs in contrast family: %d ; in FK-31 family: %d ; shared: %d"
      % (len(agg2), len(agg), len(set(agg2) & set(agg))))
for rva, n in agg2.most_common(15):
    print("   runtime.dll+0x%08X   %d" % (rva, n))
