import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
E=0x035EC850; nodes=sorted(ins)
succ={n:set(c.succ.get(n,())) for n in nodes}; pred={n:set(c.pred.get(n,())) for n in nodes}
def fwd(s):
    R=set(); st=[s]
    while st:
        n=st.pop()
        if n in R: continue
        R.add(n)
        for d in succ.get(n,()):
            if d not in R: st.append(d)
    return R
def doms():
    allN=set(nodes); D={E:{E}}
    for n in nodes:
        if n!=E: D[n]=allN.copy()
    ch=True
    while ch:
        ch=False
        for n in nodes:
            if n==E: continue
            ps=[p for p in pred.get(n,()) if p in D]
            if not ps: continue
            new=set.intersection(*[D[p] for p in ps])|{n}
            if new!=D[n]: D[n]=new; ch=True
    return D
D=doms()
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
FR={}
def fr(s):
    if s not in FR: FR[s]=fwd(s)
    return FR[s]
def guards(w):
    out=[]
    for d in sorted(D[w]):
        if d==w: continue
        i=ins[d]
        if i.mnemonic not in COND: continue
        for s in sorted(succ[d]):
            if w not in fr(s):
                out.append((d,i.mnemonic,i.op_str, s==i.operands[0].imm)); break
    return out

# ---- reaching definitions for r13 ----
def reaching_def(reg, site):
    """defs of `reg` that reach `site` along some path (backward walk stopping at defs)."""
    defs=set()
    for r in nodes:
        i=ins[r]
        try: rd,wr=i.regs_access()
        except Exception: wr=()
        if any(i.reg_name(w) in reg for w in wr): defs.add(r)
    # also treat calls as clobbering volatile regs
    VOL={'rax','rcx','rdx','r8','r9','r10','r11'}
    if reg & VOL:
        for r,t in c.calls.items(): defs.add(r)
    seen=set(); st=list(pred.get(site,())); found=set()
    while st:
        n=st.pop()
        if n in seen: continue
        seen.add(n)
        if n in defs: found.add(n); continue
        for p in pred.get(n,()): st.append(p)
    return found

print("=== reaching definitions of r13 at each `mov [rdi+0xf8], r13` site ===")
for site in (0x035ECBD1,0x035ECFE2,0x035ED5CE):
    f=reaching_def({'r13','r13d'}, site)
    print(f"  {site:#x} <- {[c.txt(x) for x in sorted(f)]}")

print("\n=== FULL guard list for the KEY sites ===")
for w,label in [(0x035ECCFB,'GRAVITY#1 write X,Y  (after NewFallVelocity 0x35ECCEF)'),
                (0x035ECD06,'GRAVITY#1 write Z'),
                (0x035ED617,'NewFallVelocity #2 CALL'),
                (0x035ED658,'GRAVITY#2 write X,Y'),
                (0x035ED946,'Q4 block write X,Y'),
                (0x035ED9BB,'CLAMP write X,Y'),
                (0x035ED9C3,'CLAMP write Z  <-- T3-A')]:
    g=guards(w)
    print(f"\n  {w:#x}  {label}   -> {len(g)} guards")
    for d,m,o,taken in g:
        # print the comparison feeding it (previous flag-setting insn)
        prev=None
        for k in sorted(nodes):
            if k<d and ins[k].mnemonic in ('cmp','test','comiss','comisd','ucomiss','ucomisd','sub','add','and','or','xor','inc','dec'):
                prev=k
        # better: nearest preceding flag setter by address within same straight line
        cand=[k for k in nodes if k<d and ins[k].mnemonic in ('cmp','test','comiss','comisd','ucomiss','ucomisd')]
        near=max(cand) if cand else None
        print(f"     {d:#010x} {m:5s} {o:12s}  ({'taken' if taken else 'fallthrough'} exits)   nearest cmp: {c.txt(near) if near else '-'}")
