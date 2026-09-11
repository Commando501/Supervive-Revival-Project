import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X=capstone.x86
im=Img(); c=CFG(im,0x035E9EC0)
# name of mask 0x01 record
def astr(rva,maxn=64):
    b=im.read(rva,maxn); out=[]
    for x in b:
        if x==0: return ''.join(out) if out else None
        if not (32<=x<127): return None
        out.append(chr(x))
    return None
v=struct.unpack('<Q',im.read(0x07f8f0b8-0x38,8))[0]-im.imagebase
print("mask 0x01 name at -0x38:",astr(v))
print()
def writers(reg, lo, hi):
    """every insn in [lo,hi) that WRITES reg (capstone regs_access)"""
    out=[]
    for r in sorted(c.insns):
        if not (lo<=r<hi): continue
        i=c.insns[r]
        try: _,w=i.regs_access()
        except Exception: continue
        for wr in w:
            nm=i.reg_name(wr)
            if nm==reg: out.append((r,i.mnemonic,i.op_str))
    return out
for reg,lo,hi,label in [('rbx',0x035E9F00,0x035EB13B,'rbx (=this/CMC) after 0x35e9efd'),
                        ('rcx',0x035E9F2E+7,0x035E9FB6,'rcx (=UpdatedComponent) between load and IsSimPhys call'),
                        ('r15',0x035E9F7F+3,0x035E9F98,'r15 (=0) between xor and cmp'),
                        ('r13',0x035E9F0D+4,0x035E9F29,'r13 (=World) between set and test')]:
    w=writers(reg,lo,hi)
    print(f"{label}: {len(w)} writer(s)")
    for x in w: print(f"    {x[0]:#010x} {x[1]} {x[2]}")
print()
# r8d at the StartNewPhysics call
for r in (0x035EB129,0x035EB12C,0x035EB130,0x035EB137,0x035EB13A):
    i=c.insns.get(r)
    print(f"  {r:#010x} {i.mnemonic} {i.op_str}" if i else f"  {r:#x} n/a")
w=writers('r8d',0x035EB12A,0x035EB13B); w2=writers('r8',0x035EB12A,0x035EB13B)
print("  writers of r8d/r8 between xor and call:",w,w2)
