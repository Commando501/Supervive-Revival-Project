"""INDEPENDENT COMPLETENESS INSTRUMENT #2: CFG every one of the 413 ULokiCMC vtable slot targets
(plus engine CMC's 413) and scan operands for disp 0x16C8. Must rediscover the same set."""
import sys, struct, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img(); IB=im.imagebase
LOKI_VT=0x088F8570; ENG_VT=0x07fbed58
def slots(vt,n=413):
    out=[]
    for d in range(0,n*8,8):
        q=struct.unpack_from('<Q',im.read(vt+d,8),0)[0]
        if IB<=q<IB+im.sizeofimage: out.append((d,q-IB))
    return out
L=slots(LOKI_VT); E=slots(ENG_VT)
print(f"LokiCMC vtable: {len(L)} in-image slots;  EngCMC: {len(E)}")
targets={r for _,r in L} | {r for _,r in E}
print(f"distinct slot targets: {len(targets)}")
dark=[t for t in targets if im.page_nonzero(t)==0]
print(f"  targets on a DARK page (all-zero, never executed in any captured process): {len(dark)}  {[hex(x) for x in sorted(dark)][:12]}")
hits=collections.defaultdict(list); scanned=0; errs=0
for t in sorted(targets):
    if im.page_nonzero(t)==0: continue
    try:
        c=CFG(im,t,maxinsn=300000); scanned+=1
    except Exception: errs+=1; continue
    for a in sorted(c.insns):
        i=c.insns[a]
        for op in i.operands:
            if op.type==X86.X86_OP_MEM and op.mem.disp==0x16C8:
                bn=i.reg_name(op.mem.base) if op.mem.base else '?'
                if bn in ('rsp','rip'): continue
                hits[t].append((a,bn,i.mnemonic+' '+i.op_str)); break
print(f"scanned {scanned} lit slot targets ({errs} CFG errors)")
print(f"\n=== instrument #2 result: {sum(len(v) for v in hits.values())} operand hits in {len(hits)} slot functions ===")
for t,v in sorted(hits.items()):
    ds=[d for d,r in L if r==t]; de=[d for d,r in E if r==t]
    print(f"  fn {t:#010x}  LokiCMCvt disps={[hex(x) for x in ds]} EngCMCvt disps={[hex(x) for x in de]}")
    for a,bn,txt in v: print(f"      {a:#010x} base={bn:<5} {txt}")
print("\n=== CROSS-CHECK vs instrument #1 (byte-superset + pdata CFG) ===")
i1={0x055C2438,0x055C2441,0x055C2469,0x055b860b}
i2={a for v in hits.values() for a,_,_ in v}
print(f"  instrument#1 CMC/vt-relevant set: {[hex(x) for x in sorted(i1)]}")
print(f"  instrument#2 set                : {[hex(x) for x in sorted(i2)]}")
print(f"  only-in-#2 (NEW): {[hex(x) for x in sorted(i2-i1)]}")
print(f"  only-in-#1     : {[hex(x) for x in sorted(i1-i2)]}")
