#!/usr/bin/env python
"""q2_bootsessions.py -- Q2: establish BOOT SESSIONS from the corpus itself and test
CLAUDE.md's [I]-graded claim that the FK-31 kill address is constant PER BOOT.

THE INSTRUMENT: on Windows, ASLR for a mapped IMAGE is chosen once per BOOT per image
file, not per process.  So two processes that share a boot session share ntdll.dll's
base; two processes in different boot sessions almost certainly do not (the randomiser
has 2^19 candidate slots for the 64-bit system region).

POSITIVE CONTROL for the instrument (method rule 1): ntdll must NOT be the only
per-boot-constant module.  kernel32 / KERNELBASE / user32 / combase / gdi32 /
advapi32 are all system images subject to the same policy, so a partition derived
from ntdll alone must be REPRODUCED, cluster-for-cluster, by each of the others.  If
one of them cuts differently, ntdll's constancy is not measuring what I claim.

NEGATIVE CONTROL: preloader.dll is loaded dynamically (not a boot-time system image),
so its base must VARY WITHIN a boot session.  If it were constant too, "constant
across two dumps" would be evidence of nothing (e.g. a dump-writer artifact).

usage: python q2_bootsessions.py [sweep.tsv]
"""
import csv
import collections
import sys
import time

TSV = sys.argv[1] if len(sys.argv) > 1 else 'scratchpad/s133/evidence/md_sweep.tsv'
rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
rows.sort(key=lambda r: int(r['create_time'] or 0))

SYS = ['ntdll', 'kernel32', 'kernelbase', 'user32', 'combase', 'advapi32', 'gdi32']

print("=" * 104)
print("Q2  BOOT SESSIONS FROM THE CORPUS  (unit: distinct crashpad reports)")
print("=" * 104)
print("reports: %d" % len(rows))

# ---- partition by ntdll base ----
byntdll = collections.OrderedDict()
for r in rows:
    byntdll.setdefault(r['ntdll'], []).append(r)
print("\ndistinct ntdll.dll bases (= candidate boot sessions): %d" % len(byntdll))

# ---- CONTROL: do the other system DLLs induce the SAME partition? ----
print("\n--- CONTROL: does each other system image induce the same partition as ntdll? ---")
base_part = {r['guid']: r['ntdll'] for r in rows}
for m in SYS[1:]:
    part = {r['guid']: r[m] for r in rows}
    # agreement = for every pair, same-ntdll  <=>  same-m
    agree = disagree = 0
    gs = [r['guid'] for r in rows]
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            a = base_part[gs[i]] == base_part[gs[j]]
            b = part[gs[i]] == part[gs[j]]
            if a == b:
                agree += 1
            else:
                disagree += 1
    nd = len(set(part.values()))
    print("   %-12s distinct bases=%-3d  pairwise agreement with ntdll partition: "
          "%d agree / %d DISAGREE" % (m, nd, agree, disagree))

# ---- NEGATIVE CONTROL: preloader must vary within a session ----
print("\n--- NEGATIVE CONTROL: preloader.dll base must VARY inside one boot session ---")
for nb, grp in byntdll.items():
    pl = collections.Counter(r['preloader_base'] for r in grp)
    print("   ntdll %-16s n=%-3d distinct preloader bases=%-3d  (most common seen %dx)"
          % (nb, len(grp), len(pl), pl.most_common(1)[0][1]))

# ---- game exe base: per boot or per launch? ----
print("\n--- SUPERVIVE-Win64-Shipping.exe base: per BOOT or per LAUNCH? ---")
for nb, grp in byntdll.items():
    gb = collections.Counter(r['game_base'] for r in grp)
    print("   ntdll %-16s n=%-3d distinct game bases=%-3d  %s"
          % (nb, len(grp), len(gb), dict(gb)))

# ---- the payoff: kill address vs boot session ----
print("\n" + "=" * 104)
print("THE TEST: is the FK-31 kill address constant WITHIN a boot session, and different"
      " BETWEEN them?")
print("=" * 104)
fam = [r for r in rows if r['exc_code'] == '0xC0000005' and r['exc_p0'] == '0x8'
       and r['exc_addr'] and int(r['exc_addr'], 16) & 0xFFF == 1]
print("FK-31-family reports: %d of %d" % (len(fam), len(rows)))
print("%-18s %-6s %-6s %-22s %-22s %s"
      % ("ntdll base", "n_all", "n_fam", "date span (ProcessCreateTime)",
         "distinct kill addrs", "kill addr(s)"))
for nb, grp in byntdll.items():
    f = [r for r in grp if r in fam]
    ts = [int(r['create_time']) for r in grp if r['create_time']]
    span = "%s .. %s" % (time.strftime('%Y-%m-%d %H:%M', time.localtime(min(ts))),
                         time.strftime('%m-%d %H:%M', time.localtime(max(ts)))) if ts else "?"
    ka = collections.Counter(r['exc_addr'] for r in f)
    print("%-18s %-6d %-6d %-38s %-6d %s"
          % (nb, len(grp), len(f), span, len(ka),
             ', '.join('%s x%d' % (k, v) for k, v in ka.most_common())))

# ---- does the whole corpus ever show two kill addresses in ONE session? ----
bad = [nb for nb, grp in byntdll.items()
       if len(set(r['exc_addr'] for r in grp if r in fam)) > 1]
print("\nboot sessions with MORE THAN ONE distinct FK-31 kill address: %d %s"
      % (len(bad), bad))
addr_sessions = collections.defaultdict(set)
for r in fam:
    addr_sessions[r['exc_addr']].add(r['ntdll'])
print("kill addresses appearing in MORE THAN ONE boot session: %s"
      % {a: sorted(s) for a, s in addr_sessions.items() if len(s) > 1})

# ---- is the kill address a fixed offset from any system module? ----
print("\n--- is kill_addr - <module base> constant across boot sessions? ---")
for m in SYS + ['game_base', 'preloader_base']:
    deltas = collections.Counter()
    for r in fam:
        if r[m] and r['exc_addr']:
            deltas['0x%X' % (int(r['exc_addr'], 16) - int(r[m], 16))] += 1
    print("   kill - %-14s : %d distinct deltas  %s"
          % (m, len(deltas), dict(deltas) if len(deltas) <= 6 else '...'))

# ---- non-family reports: what are they and which session ----
print("\n--- the %d reports OUTSIDE the FK-31 family ---" % (len(rows) - len(fam)))
for r in rows:
    if r in fam:
        continue
    print("   %s  %s  code=%s p0=%s addr=%s rip=%s ripmod=%s+%s  ntdll=%s"
          % (r['create_iso'], r['guid'][:8], r['exc_code'], r['exc_p0'], r['exc_addr'],
             r['rip'], r['rip_mod'] or '-', r['rip_rva'] or '-', r['ntdll']))
