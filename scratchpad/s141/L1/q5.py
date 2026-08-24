import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
nodes=sorted(ins); pred={n:set(c.pred.get(n,())) for n in nodes}
def rdef(regs, site):
    defs=set()
    for r in nodes:
        i=ins[r]
        try: rd,wr=i.regs_access()
        except Exception: wr=()
        if any(i.reg_name(w) in regs for w in wr): defs.add(r)
    seen=set(); st=list(pred.get(site,())); found=set()
    while st:
        n=st.pop()
        if n in seen: continue
        seen.add(n)
        if n in defs: found.add(n); continue
        for p in pred.get(n,()): st.append(p)
    return found
print("=== reaching defs of xmm13/xmm14 at the 0x35ED658/0x35ED65C writes ===")
for site,reg in [(0x035ED658,{'xmm13'}),(0x035ED65C,{'xmm14'})]:
    print(f"  {site:#x} {list(reg)[0]} <- ")
    for d in sorted(rdef(reg,site)): print(f"       {c.txt(d)}")
print("\n=== Q5: SOUND EXIT SETS (edges u->v, u in R, v not in R; u not a call) ===")
for tgt,label in [(0x035ECA2C,'FIRST Velocity write 0x35ECA2C'),
                  (0x035ECCEF,'GRAVITY site (NewFallVelocity call) 0x35ECCEF'),
                  (0x035ED9BB,'the CLAMP write 0x35ED9BB')]:
    ex,R=c.exits_from(tgt)
    real=[(u,v) for u,v in ex if ins[u].mnemonic!='call']
    back=[(u,v) for u,v in real if v is not None and v<u]
    print(f"\n  --- {label}:  |R|={len(R)}   exit edges={len(real)}   BACKWARD exit edges={len(back)}")
    for u,v in real:
        i=ins[u]
        vs=f"{v:#x}" if v is not None else 'TERMINATOR'
        print(f"     {u:#010x} {i.mnemonic:5s} {i.op_str:16s} -> {vs}{'   *** BACKWARD ***' if (v is not None and v<u) else ''}")
    # dead-ends
    de=[n for n in R if n!=tgt and not c.succ.get(n) and ins[n].mnemonic not in ('ret','retf')]
    print(f"     dead-ended nodes in R (should be 0): {len(de)}")
