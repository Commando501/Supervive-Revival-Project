#!/usr/bin/env python
"""q1d_shadow_exe.py -- the THIRD hidden image: a MEM_IMAGE allocation whose span equals
SUPERVIVE-Win64-Shipping.exe's SizeOfImage (0xA9E1000), present in 124/124 reports, at a
different address every process, absent from the ModuleList.

Never recorded anywhere in this project.  Characterise it: state, protection, whether the
minidump carries any of its bytes, and whether its address relates to anything known.

POSITIVE CONTROL: the REAL game image (the ModuleList entry) is printed in the same table
with the same fields, from the same code path.  If the two are indistinguishable the
"shadow" framing is wrong; if the real one shows the usual multi-region section split and
the shadow shows one uniform region, they are different objects.

usage: python q1d_shadow_exe.py [sweep.tsv]
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump, STATE, TYPE, protname             # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402

TSV = sys.argv[1] if len(sys.argv) > 1 else 'scratchpad/s133/evidence/md_sweep.tsv'
rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))
GAME_SPAN = 0xA9E1000

print("=" * 104)
print("Q1d  THE SHADOW GAME IMAGE  (MEM_IMAGE, span 0x%X, not in ModuleList)" % GAME_SPAN)
print("=" * 104)

shapes = collections.Counter()
real_shapes = collections.Counter()
align = collections.Counter()
samples = []
for r in rows:
    d = Dump(r['first_path'])
    if not d.ok:
        continue
    mi = fast_meminfo(r['first_path'], d.streams)
    groups = collections.defaultdict(list)
    for x in mi:
        if x[6] == 0x1000000:
            groups[x[1]].append(x)
    gb = int(r['game_base'], 16) if r['game_base'] else 0
    for ab, g in groups.items():
        span = sum(y[3] for y in g)
        if span != GAME_SPAN:
            continue
        hidden = not d.modof(ab)
        key = (hidden, len(g),
               tuple(sorted(set((STATE.get(y[4], hex(y[4])), protname(y[5])) for y in g))))
        (shapes if hidden else real_shapes)[key] += 1
        if hidden:
            align[ab & 0xFFFFFFFF] += 1
            if len(samples) < 6:
                samples.append((r, ab, sorted(g)))

print("\nHIDDEN (not in ModuleList) shapes -> reports:")
for k, n in shapes.most_common():
    print("   hidden=%s regions=%d states/prots=%s  -> %d reports" % (k[0], k[1], k[2], n))
print("\nCONTROL - the REAL game image (IS in ModuleList) shapes -> reports:")
for k, n in real_shapes.most_common(8):
    print("   hidden=%s regions=%d states/prots=%s  -> %d reports" % (k[0], k[1], k[2], n))

print("\nlow-32-bit alignment of the shadow base (unit: reports):")
for a, n in align.most_common(10):
    print("   ...0x%08X  %d" % (a, n))

print("\n--- sample shadow allocations, full region rows ---")
for r, ab, g in samples:
    print("\n  %s %s  shadow base 0x%X   game_base %s   delta 0x%X"
          % (r['create_iso'], r['guid'][:8], ab, r['game_base'],
             ab - int(r['game_base'], 16) if r['game_base'] else 0))
    for (b, a2, ap, sz, st, pr, ty) in g:
        print("     +0x%08X size 0x%08X  state=%-8s prot=%-14s aprot=%-16s type=%s"
              % (b - ab, sz, STATE.get(st, hex(st)), protname(pr), protname(ap),
                 TYPE.get(ty, hex(ty))))

# Does the dump carry any BYTES of the shadow?  (MemoryList / Memory64List coverage)
print("\n--- does MemoryList carry any shadow bytes? ---")
import struct                                                   # noqa: E402
for r, ab, g in samples[:3]:
    d = Dump(r['first_path'])
    ranges = []
    if 5 in d.streams:
        for _ds, rva in d.streams[5]:
            n = struct.unpack('<I', d._at(rva, 4))[0]
            blob = d._at(rva + 4, n * 16)
            for i in range(n):
                sa = struct.unpack_from('<Q', blob, i * 16)[0]
                sz = struct.unpack_from('<I', blob, i * 16 + 8)[0]
                ranges.append((sa, sz))
    hit = [(hex(sa), hex(sz)) for sa, sz in ranges if sa < ab + GAME_SPAN and sa + sz > ab]
    print("   %s  MemoryList ranges=%d  overlapping the shadow: %d %s"
          % (r['guid'][:8], len(ranges), len(hit), hit[:4]))
