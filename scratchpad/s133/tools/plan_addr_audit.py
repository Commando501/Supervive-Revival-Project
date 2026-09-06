#!/usr/bin/env python3
"""FK-20 made concrete: which addresses the project's docs cite as GAME FUNCTIONS are DARK?

Noise filter: a cited hex value counts only if it is a real function BeginAddress in the
382,704-entry .pdata union (i.e. the packer's own runtime function table says a function
starts exactly there). That excludes runtime.dll RVAs, exit codes, offsets and struct sizes.
POSITIVE CONTROL: known-live addresses (ProcessInternal 0x13454A0, GoToPhase 0x5601020) must
be accepted by the filter and graded LIT; a known-dark one must be graded DARK."""
import re, glob, csv, collections, io, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PAGE=4096; TEXT_RVA=0x1000; TEXT_VSZ=0x7649000
NP=TEXT_VSZ//PAGE+(1 if TEXT_VSZ%PAGE else 0)
f=open('dumps/merged6.dump.exe','rb'); lit=bytearray(NP); f.seek(TEXT_RVA)
for i in range(NP):
    b=f.read(PAGE)
    if not b: break
    if b.count(0)!=len(b): lit[i]=1
begins=set()
with open('tools/strxref/index/pdata_union.csv') as fh:
    for d in csv.DictReader(fh): begins.add(int(d['begin_rva'],16))
print(f"[CTRL] function BeginAddresses in the .pdata union: {len(begins)}")
def isfn(r): return r in begins
def st(r): return 'LIT' if lit[(r-TEXT_RVA)//PAGE] else 'DARK'
for nm,r in [('ProcessInternal',0x13454A0),('GoToPhase impl',0x5601020),('Respawn (AS)',0x5A6AC40)]:
    print(f"[CTRL] {nm:18s} {r:#010x} is-a-function={isfn(r)} state={st(r)}")
print()
SRC=['CLAUDE.md']+sorted(glob.glob('docs/*.md'))
pat=re.compile(r'0x0?([0-9A-Fa-f]{6,8})\b')
hits=collections.defaultdict(list)
for p in SRC:
    try: txt=open(p,encoding='utf-8',errors='replace').read().splitlines()
    except Exception: continue
    for ln,line in enumerate(txt,1):
        if 'runtime.dll' in line or 'packer' in line: continue
        for m in pat.finditer(line):
            r=int(m.group(1),16)
            if TEXT_RVA<=r<TEXT_RVA+TEXT_VSZ and isfn(r):
                hits[r].append((p,ln,line.strip()[:130]))
dark=[r for r in hits if st(r)=='DARK']
print(f"distinct cited GAME FUNCTION addresses across {len(SRC)} docs: {len(hits)}")
print(f"  readable in merged6 : {len(hits)-len(dark)}")
print(f"  DARK in merged6     : {len(dark)}  <- the docs name them; we cannot disassemble them")
print()
for r in sorted(dark, key=lambda r:-len(hits[r])):
    print(f"  {r:#010x}  cited {len(hits[r])}x")
    for p,ln,c in hits[r][:2]: print(f"      {p}:{ln}  {c}")
with open('scratchpad/s133/evidence/dark_cited_functions.txt','w',encoding='utf-8') as o:
    for r in sorted(dark, key=lambda r:-len(hits[r])):
        o.write(f"{r:#010x}\t{len(hits[r])}\n")
        for p,ln,c in hits[r]: o.write(f"\t{p}:{ln}\t{c}\n")
