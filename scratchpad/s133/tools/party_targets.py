#!/usr/bin/env python3
"""PRE-REGISTRATION for the S133 queue/party action sweep.
Enumerate every UPartyManager (and sibling) UFunction impl whose page is DARK in merged6.
These are the pages the experiment predicts will light."""
import csv, io, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PAGE=4096; TEXT_RVA=0x1000; TEXT_VSZ=0x7649000
NP=TEXT_VSZ//PAGE + (1 if TEXT_VSZ%PAGE else 0)
f=open('dumps/merged6.dump.exe','rb'); lit=bytearray(NP); f.seek(TEXT_RVA)
for i in range(NP):
    b=f.read(PAGE)
    if not b: break
    if b.count(0)!=len(b): lit[i]=1
def st(r): return 'LIT' if lit[(r-TEXT_RVA)//PAGE] else 'DARK'
def pg(r): return (r-TEXT_RVA)//PAGE

rows=list(csv.DictReader(io.open('scratchpad/s131/lane-d-empty-impl-census.tsv',encoding='utf-8',errors='replace'),delimiter='\t'))
CLASSES=['PartyManager','PartyModel','SocialManager','ChatManager','StorefrontManager',
         'PersonalizationManager','PlatformInventoryManager','MatchmakingManager','LobbyManager']
print("[CTRL] instrument: known-LIT ProcessInternal 0x13454A0 ->", st(0x13454A0),
      "| known-DARK TryJoinQueue 0x5875E90 ->", st(0x5875E90))
print()
darkpages=collections.defaultdict(set); tally=collections.Counter()
for r in rows:
    cls=r['class']; 
    if not any(c in cls for c in CLASSES): continue
    try: rva=int(r['impl_rva'],16)
    except Exception: continue
    if not (TEXT_RVA<=rva<TEXT_RVA+TEXT_VSZ): continue
    s=st(rva); tally[(cls.split('.')[-1],s)]+=1
    if s=='DARK': darkpages[cls].add(pg(rva))
print("PRE-REGISTERED TARGETS — dark impls by class")
tot=set()
for cls in sorted(darkpages):
    ps=sorted(darkpages[cls]); tot|=set(ps)
    n=sum(1 for r in rows if r['class']==cls and r['impl_rva'].startswith('0x') and st(int(r['impl_rva'],16))=='DARK')
    print(f"  {cls:34s} {n:3d} dark impls on {len(ps):2d} dark page(s): "
          + ", ".join(hex(TEXT_RVA+p*PAGE) for p in ps))
print()
print(f"TOTAL DISTINCT DARK PAGES ACROSS THESE CLASSES: {len(tot)}")
print("  " + ", ".join(hex(TEXT_RVA+p*PAGE) for p in sorted(tot)))
print()
print("NAMED HEADLINE TARGETS:")
for nm,rva in [('UPartyManager::TryJoinQueue',0x5875E90),('UPartyManager span lo',0x5873280),
               ('UPartyManager span hi',0x5879EE0)]:
    print(f"  {nm:32s} {rva:#010x} page {TEXT_RVA+pg(rva)*PAGE:#010x} -> {st(rva)}")
print()
print("Dark impls in the UPartyManager span 0x5873280-0x5879EE0:")
for r in sorted(rows,key=lambda r:r['impl_rva']):
    try: rva=int(r['impl_rva'],16)
    except Exception: continue
    if 0x5873280<=rva<=0x5879EE0 and st(rva)=='DARK':
        print(f"   {rva:#010x} page {TEXT_RVA+pg(rva)*PAGE:#010x}  {r['class']}::{r['func']}  [{r['verdict']}]")
