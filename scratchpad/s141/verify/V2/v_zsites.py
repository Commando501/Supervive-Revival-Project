import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,und,ind=cfg(I,0x035EC850); P=preds(succ)
Zw = {0x035ECBD1,0x035ECFE2,0x035ED5CE}
Zrestore = {0x035ECBDE}
def fwd_until_Zwrite(start, limit=400):
    """walk forward from start; report the first write to Velocity.Z (rsi+0x10 or rdi+0xf8) on each path"""
    seen=set(); st=[start]; hits=[]
    n=0
    while st and n<limit:
        a=st.pop(); n+=1
        if a in seen: continue
        seen.add(a)
        i=ins.get(a)
        if i is None: continue
        o=mem_writes(i)
        if o is not None:
            b=i.reg_name(o.mem.base) if o.mem.base else ''
            if (b=='rsi' and o.mem.disp==0x10) or (b=='rdi' and o.mem.disp==0xf8):
                hits.append((a,i.mnemonic,i.op_str)); continue
        for s in succ.get(a,()): st.append(s)
    return hits
for z in sorted(Zw):
    nxt = list(succ[z])[0]
    hits = fwd_until_Zwrite(nxt)
    print("Velocity.Z := 0 at %08x  -> next Z-writes on forward paths: %s" %
          (z, [(hex(a),m+' '+op) for a,m,op in hits][:6] or "NONE (the zero STANDS on every path)"))
print()
print("=== guards immediately controlling 0x035ECFE2 (the un-restored one) ===")
b=0x035ECFE2
chain=[]
cur=b
for _ in range(14):
    pr=sorted(P.get(cur,()))
    if len(pr)!=1: chain.append((cur,pr)); break
    cur=pr[0]; chain.append((cur,None))
for a,pr in chain:
    i=ins[a]
    print("   %08x %-20s %-8s %-34s %s" % (a,i.bytes.hex(),i.mnemonic,i.op_str,
          ("preds={%s}"%','.join('%x'%x for x in pr)) if pr else ""))
print()
print("=== TRUE Velocity-store enumeration (any base aliasing this+0xE8) ===")
sites={}
for a in sorted(ins):
    o=mem_writes(ins[a])
    if o is None or not o.mem.base: continue
    bs=ins[a].reg_name(o.mem.base); d=o.mem.disp
    if bs=='rsi' and 0<=d<=0x18: sites.setdefault('rsi',[]).append(a)
    if bs=='rdi' and 0xE8<=d<0x100: sites.setdefault('rdi',[]).append(a)
print("   via rsi: %d stores ; via rdi+0xE8..0xFF: %d stores ; TOTAL %d" %
      (len(sites['rsi']),len(sites['rdi']),len(sites['rsi'])+len(sites['rdi'])))
print("   L2 reported: 32 stores at 16 sites, scan described as 'Exhaustive'.")
