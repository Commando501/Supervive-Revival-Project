#!/usr/bin/env python3
"""FK-20 made concrete, v2.

v1 DEFECT (caught by its own positive control, recorded here): it filtered cited addresses
through membership in the .pdata union's BeginAddress set. That set is built ONLY from
MATERIALISED (decrypted) functions -- pdataunion.py discards placeholders -- so the filter
can only ever admit LIT functions and reported "1 dark of 520". Degenerate by construction.
The control that caught it: 0x5A6AC40 (ULokiRespawnComponent::Respawn, known dark) was
graded is-a-function=False and thus excluded.

v2 filter, chosen to be independent of decryption state:
  - the cited value must lie in RVA [0x1000000, .text end) -- zone B/C, where every game
    function this project has ever named lives; below 16 MB is pre-engine third-party code
    that no doc cites as a target, and the < 16 MB range is where struct offsets alias.
  - the citing LINE must not mention runtime.dll / packer / preloader (those are a different
    module's RVAs).
"""
import re, glob, collections, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PAGE=4096; TEXT_RVA=0x1000; TEXT_VSZ=0x7649000
NP=TEXT_VSZ//PAGE+(1 if TEXT_VSZ%PAGE else 0)
f=open('dumps/merged6.dump.exe','rb'); lit=bytearray(NP); f.seek(TEXT_RVA)
for i in range(NP):
    b=f.read(PAGE)
    if not b: break
    if b.count(0)!=len(b): lit[i]=1
def st(r): return 'LIT' if lit[(r-TEXT_RVA)//PAGE] else 'DARK'
print("[CTRL] instrument must grade a known-LIT and a known-DARK address correctly:")
for nm,r,exp in [('ProcessInternal',0x13454A0,'LIT'),('GoToPhase impl',0x5601020,'LIT'),
                 ('AuthPlayerDetachPlayerFromRidable',0x55CCCB0,'LIT'),
                 ('ULokiRespawnComponent::Respawn',0x5A6AC40,'DARK')]:
    got=st(r); print(f"   {nm:36s} {r:#010x} -> {got}  {'PASS' if got==exp else 'FAIL'}")
print()
SRC=['CLAUDE.md']+sorted(glob.glob('docs/*.md'))
pat=re.compile(r'0x0?([0-9A-Fa-f]{6,8})\b')
hits=collections.defaultdict(list)
for p in SRC:
    try: txt=open(p,encoding='utf-8',errors='replace').read().splitlines()
    except Exception: continue
    for ln,line in enumerate(txt,1):
        low=line.lower()
        if 'runtime.dll' in low or 'packer' in low or 'preloader' in low: continue
        for m in pat.finditer(line):
            r=int(m.group(1),16)
            if 0x1000000<=r<TEXT_RVA+TEXT_VSZ: hits[r].append((p,ln,line.strip()[:130]))
dark=[r for r in hits if st(r)=='DARK']
print(f"distinct cited addresses in RVA >=16 MB across {len(SRC)} docs: {len(hits)}")
print(f"  readable in merged6 : {len(hits)-len(dark)} ({(len(hits)-len(dark))/len(hits)*100:.1f}%)")
print(f"  DARK in merged6     : {len(dark)} ({len(dark)/len(hits)*100:.1f}%)  <- named in the docs, unreadable")
print()
print("DARK cited addresses, most-cited first:")
for r in sorted(dark, key=lambda r:-len(hits[r]))[:40]:
    print(f"  {r:#010x}  cited {len(hits[r])}x")
    for p,ln,c in hits[r][:2]: print(f"      {p}:{ln}  {c}")
with open('scratchpad/s133/evidence/dark_cited_functions.txt','w',encoding='utf-8') as o:
    o.write(f"# cited addresses RVA>=0x1000000 that are DARK in dumps/merged6.dump.exe\n")
    for r in sorted(dark, key=lambda r:-len(hits[r])):
        o.write(f"{r:#010x}\t{len(hits[r])}\n")
        for p,ln,c in hits[r]: o.write(f"\t{p}:{ln}\t{c}\n")
print(f"\nwrote scratchpad/s133/evidence/dark_cited_functions.txt ({len(dark)} entries)")
