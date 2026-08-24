import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img(); p=CFG(im,0x055B8370)

print("=== all defs of r15 / r15d / r15b inside ULokiCMC::PerformMovement ===")
for a in sorted(p.insns):
    i=p.insns[a]
    try: rd,wr=i.regs_access()
    except Exception: rd,wr=(),()
    wnames={i.reg_name(r) for r in wr}
    if wnames & {'r15','r15d','r15w','r15b'}:
        print(f"   {a:#010x}  {i.bytes.hex(' '):<22} {i.mnemonic} {i.op_str}")
print()
print("=== all defs of rsi (for comparison; +0x12B0 lane uses rsi) ===")
for a in sorted(p.insns):
    i=p.insns[a]
    try: rd,wr=i.regs_access()
    except Exception: rd,wr=(),()
    if {i.reg_name(r) for r in wr} & {'rsi','esi','si','sil'}:
        print(f"   {a:#010x}  {i.bytes.hex(' '):<22} {i.mnemonic} {i.op_str}")
print()
print("=== region 0x055B85A0 .. 0x055B8650 in CFG order ===")
for a in sorted(x for x in p.insns if 0x055B85A0 <= x <= 0x055B8650):
    print(f"   {p.txt(a)}    succ={[hex(s) for s in sorted(p.succ.get(a,()))]}")
