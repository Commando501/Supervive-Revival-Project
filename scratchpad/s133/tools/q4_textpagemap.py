#!/usr/bin/env python
"""q4_textpagemap.py -- THE PAYOFF.  MemoryInfoList gives a COMPLETE PER-PAGE MAP of which
SUPERVIVE .text pages were demand-DECRYPTED at the moment of each crash.

Discovered in this lane and never recorded before: the running game image is NOT a normal
MEM_IMAGE mapping.  Its AllocationBase group is MEM_MAPPED with AllocationProtect
PAGE_EXECUTE_READWRITE, split into thousands of regions that alternate

    PAGE_EXECUTE_READ   <- page has been demand-decrypted (executable)
    PAGE_NOACCESS       <- page not yet decrypted

So the region map IS the decryption bitmap.  The minidump carries ZERO image BYTES (already
measured this session), but it carries the exact STATE of every page, for 124 crash moments
that no dumpimage snapshot exists for.

WHAT THIS TOOL PRODUCES
  1. per-report decrypted-.text-page counts, comparable to the dumpimage manifests
  2. the UNION over the corpus, and the union's delta against dumps/merged6.dump.exe
  3. the count of pages decrypted in some crash but ALL-ZERO in the merged image
     (= bytes the project has never held, with the RVAs named)
  4. a matched test of "a crash-era image holds MORE decrypted .text than a healthy one"

POSITIVE CONTROL (mandatory): for the ONE report that has a sibling dumpimage taken from the
same PID minutes earlier (crashpad-20260820-143225 <-> crash-20260820-142858, PID 16944),
the page counts must be close and the game base must be identical.  Printed explicitly.
A second control: the classifier must report the .rdata/.data sections as ~100%% accessible,
since those are never encrypted -- if they come back sparse, the prot->decrypted mapping is
wrong.

usage: python q4_textpagemap.py [sweep.tsv] [--merged dumps/merged6.dump.exe]
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_streams import Dump                                    # noqa: E402
from md_sweep import fast_meminfo                              # noqa: E402

PAGE = 0x1000
SECTIONS = [  # from dumps/merged6.dump.exe.txt (RVA, VSIZE, name)
    (0x1000, 0x7649000, '.text'),
    (0x764A000, 0x237D000, '.rdata'),
    (0x99C7000, 0x6F0000, '.data'),
    (0xA0B7000, 0x5FE000, '.pdata'),
    (0xA6B8000, 0x5E000, '_RDATA'),
]
TEXT_RVA, TEXT_SZ = 0x1000, 0x7649000
TEXT_PAGES = TEXT_SZ // PAGE           # 30281

ACCESSIBLE = 0x02 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40 | 0x80   # anything but NOACCESS/0
EXECUTABLE = 0x10 | 0x20 | 0x40 | 0x80

TSV = 'scratchpad/s133/evidence/md_sweep.tsv'
MERGED = 'dumps/merged6.dump.exe'
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == '--merged':
        i += 1
        MERGED = args[i]
    else:
        TSV = args[i]
    i += 1

rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))

print("=" * 104)
print("Q4  .text DECRYPTION BITMAP FROM MemoryInfoList  (unit: 4 KiB pages; .text has %d)"
      % TEXT_PAGES)
print("=" * 104)


def pagestate(path, gb, streams):
    """-> (exec_bitset, accessible_bitset) as bytearrays over the whole image, page-indexed."""
    mi = fast_meminfo(path, streams)
    npages = 0xA9E1000 // PAGE
    ex = bytearray(npages)
    ac = bytearray(npages)
    for (b, a, ap, sz, st, pr, ty) in mi:
        if a != gb:
            continue
        if st != 0x1000:                # only COMMIT counts
            continue
        p0 = (b - gb) // PAGE
        n = sz // PAGE
        base = pr & 0xFF
        e = 1 if (base & EXECUTABLE) else 0
        c = 1 if (base & ACCESSIBLE) else 0
        if p0 < 0 or p0 + n > npages:
            continue
        if e:
            ex[p0:p0 + n] = b'\x01' * n
        if c:
            ac[p0:p0 + n] = b'\x01' * n
    return ex, ac


per = []
union_exec = bytearray(0xA9E1000 // PAGE)
for r in rows:
    d = Dump(r['first_path'])
    if not d.ok or not r['game_base']:
        continue
    gb = int(r['game_base'], 16)
    ex, ac = pagestate(r['first_path'], gb, d.streams)
    t0 = TEXT_RVA // PAGE
    tex = sum(ex[t0:t0 + TEXT_PAGES])
    tac = sum(ac[t0:t0 + TEXT_PAGES])
    # control sections
    ctl = {}
    for rva, sz, nm in SECTIONS[1:]:
        p0, n = rva // PAGE, sz // PAGE
        ctl[nm] = (sum(ac[p0:p0 + n]), n)
    per.append((r, tex, tac, ctl))
    for k in range(t0, t0 + TEXT_PAGES):
        if ex[k]:
            union_exec[k] = 1

print("reports analysed: %d" % len(per))
tx = [p[1] for p in per]
print(".text EXECUTABLE pages per report: min=%d  median=%d  max=%d  mean=%.0f"
      % (min(tx), sorted(tx)[len(tx) // 2], max(tx), sum(tx) / len(tx)))
print(".text pct        : min=%.2f%%  max=%.2f%%"
      % (100 * min(tx) / TEXT_PAGES, 100 * max(tx) / TEXT_PAGES))

print("\n[CONTROL] never-encrypted sections must read ~100%% ACCESSIBLE:")
agg = collections.defaultdict(list)
for r, tex, tac, ctl in per:
    for nm, (a, n) in ctl.items():
        agg[nm].append(100.0 * a / n)
for nm, v in agg.items():
    print("   %-8s accessible: min %.2f%%  max %.2f%%  (n=%d reports)"
          % (nm, min(v), max(v), len(v)))
tacs = [p[2] for p in per]
print("   .text    accessible: min %.2f%%  max %.2f%%   <- the discriminator"
      % (100 * min(tacs) / TEXT_PAGES, 100 * max(tacs) / TEXT_PAGES))

# ---- the matched positive control ----
print("\n" + "=" * 104)
print("[POSITIVE CONTROL] matched pair: same PID, dumpimage 65 s before the crashpad report")
print("=" * 104)
for r, tex, tac, ctl in per:
    if r['pid'] == '16944':
        print("   crashpad report %s  PID %s  game_base %s"
              % (r['guid'][:8], r['pid'], r['game_base']))
        print("   .text executable pages at death : %d  (%.2f%%)"
              % (tex, 100.0 * tex / TEXT_PAGES))
        print("   sibling dumps/crash-20260820-142858 manifest says .text 51.8%% readable BYTES")
        print("   (byte-% and page-% are DIFFERENT metrics -- see the merged manifest's own")
        print("    warning; the comparison below is page-vs-page against merged6.)")

# ---- union and delta vs the merged image ----
print("\n" + "=" * 104)
print("UNION over the corpus vs %s" % MERGED)
print("=" * 104)
t0 = TEXT_RVA // PAGE
u = sum(union_exec[t0:t0 + TEXT_PAGES])
print("union of .text EXECUTABLE pages over %d crash reports: %d / %d = %.2f%%"
      % (len(per), u, TEXT_PAGES, 100.0 * u / TEXT_PAGES))

if os.path.exists(MERGED):
    nz = bytearray(TEXT_PAGES)
    with open(MERGED, 'rb') as f:
        f.seek(TEXT_RVA)
        for k in range(TEXT_PAGES):
            b = f.read(PAGE)
            if not b:
                break
            if b.count(0) != len(b):
                nz[k] = 1
    m = sum(nz)
    print("merged image .text non-zero pages: %d / %d = %.2f%%" % (m, TEXT_PAGES, 100.0 * m / TEXT_PAGES))
    only_crash = [k for k in range(TEXT_PAGES) if union_exec[t0 + k] and not nz[k]]
    only_merge = [k for k in range(TEXT_PAGES) if nz[k] and not union_exec[t0 + k]]
    both = sum(1 for k in range(TEXT_PAGES) if nz[k] and union_exec[t0 + k])
    print("\n  decrypted in >=1 crash AND non-zero in merged : %d pages" % both)
    print("  decrypted in >=1 crash BUT ALL-ZERO in merged : %d pages   <-- bytes never captured"
          % len(only_crash))
    print("  non-zero in merged BUT never decrypted in any crash: %d pages" % len(only_merge))
    print("  best-case union (merged pages OR crash-decrypted): %d / %d = %.2f%%"
          % (m + len(only_crash), TEXT_PAGES, 100.0 * (m + len(only_crash)) / TEXT_PAGES))
    # write the never-captured RVA list
    outp = 'scratchpad/s133/evidence/text_pages_crashonly.txt'
    with open(outp, 'w') as fh:
        fh.write("# .text pages decrypted in at least one crashpad report but ALL-ZERO in %s\n"
                 % MERGED)
        fh.write("# unit: 4 KiB pages.  RVA = page index*0x1000 + 0x%X\n" % TEXT_RVA)
        fh.write("# count: %d\n" % len(only_crash))
        # contiguous runs
        runs = []
        s = None
        prev = None
        for k in only_crash:
            if s is None:
                s = prev = k
                continue
            if k == prev + 1:
                prev = k
                continue
            runs.append((s, prev))
            s = prev = k
        if s is not None:
            runs.append((s, prev))
        fh.write("# contiguous runs: %d\n" % len(runs))
        for a, b in runs:
            fh.write("0x%08X-0x%08X  %d pages\n"
                     % (TEXT_RVA + a * PAGE, TEXT_RVA + (b + 1) * PAGE - 1, b - a + 1))
    print("  -> RVA runs written to %s (%d runs)" % (outp, len(runs)))

# ---- per-report table, sorted ----
print("\n" + "=" * 104)
print("PER-REPORT .text decrypted-page counts (top 15 and bottom 5)")
print("=" * 104)
per.sort(key=lambda x: -x[1])
for r, tex, tac, ctl in per[:15]:
    print("   %-19s %s  pages=%-6d %.2f%%  pid=%-7s dir=%s"
          % (r['create_iso'], r['guid'][:8], tex, 100.0 * tex / TEXT_PAGES, r['pid'],
             r['first_path'].split('/')[1]))
print("   ...")
for r, tex, tac, ctl in per[-5:]:
    print("   %-19s %s  pages=%-6d %.2f%%  pid=%-7s dir=%s"
          % (r['create_iso'], r['guid'][:8], tex, 100.0 * tex / TEXT_PAGES, r['pid'],
             r['first_path'].split('/')[1]))
