#!/usr/bin/env python3
"""FK-20 PAYOFF: re-grade every "this page is undecrypted / coverage-blocked" claim in the
repo against dumps/merged6.dump.exe (the union of all 26 state images, 16,694/30,281 pages).

Method: find doc lines asserting coverage blindness; extract the .text RVAs on that line;
report which of those addresses are NOW readable. An address that is now LIT means the
claim on that line is STALE and the analysis it blocked can be redone offline for free.

POSITIVE CONTROL: the grader must return LIT for ProcessInternal and DARK for 0x5875E90
(TryJoinQueue, asserted 100% zero in every dump)."""
import re, glob, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PAGE=4096; TEXT_RVA=0x1000; TEXT_VSZ=0x7649000
NP=TEXT_VSZ//PAGE+(1 if TEXT_VSZ%PAGE else 0)
f=open('dumps/merged6.dump.exe','rb'); lit=bytearray(NP); f.seek(TEXT_RVA)
for i in range(NP):
    b=f.read(PAGE)
    if not b: break
    if b.count(0)!=len(b): lit[i]=1
def st(r): return 'LIT' if lit[(r-TEXT_RVA)//PAGE] else 'DARK'
print(f"[CTRL] ProcessInternal 0x13454A0 -> {st(0x13454A0)} (expect LIT)")
print(f"[CTRL] TryJoinQueue   0x5875E90 -> {st(0x5875E90)} (expect DARK)")
print()
CLAIM=re.compile(r'coverage.?blocked|all-zero page|never decrypted|undecrypted|100\s?% zero|zero in every dump|not decrypted', re.I)
ADDR=re.compile(r'0x0?([0-9A-Fa-f]{6,8})\b')
stale=[]; still=[]
for p in ['CLAUDE.md']+sorted(glob.glob('docs/*.md')):
    try: lines=open(p,encoding='utf-8',errors='replace').read().splitlines()
    except Exception: continue
    for ln,line in enumerate(lines,1):
        if not CLAIM.search(line): continue
        low=line.lower()
        if 'runtime.dll' in low or 'packer' in low or 'preloader' in low: continue
        rs=[int(m.group(1),16) for m in ADDR.finditer(line)]
        rs=[r for r in rs if 0x1000000<=r<TEXT_RVA+TEXT_VSZ]
        if not rs: continue
        L=[r for r in rs if st(r)=='LIT']; D=[r for r in rs if st(r)=='DARK']
        if L: stale.append((p,ln,L,D,line.strip()[:170]))
        else: still.append((p,ln,D,line.strip()[:120]))
print(f"lines asserting coverage-blindness WITH a >=16MB .text RVA on them: {len(stale)+len(still)}")
print(f"  now STALE (>=1 named address is READABLE in merged6): {len(stale)}")
print(f"  still accurate (all named addresses still dark)     : {len(still)}")
print()
print("=== STALE COVERAGE-BLINDNESS CLAIMS (the analysis they blocked is now free) ===")
for p,ln,L,D,c in stale:
    print(f"  {p}:{ln}")
    print(f"     NOW READABLE: {', '.join(hex(r) for r in L)}" + (f"   still dark: {', '.join(hex(r) for r in D)}" if D else ""))
    print(f"     {c}")
