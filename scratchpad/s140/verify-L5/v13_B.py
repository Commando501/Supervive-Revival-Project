import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
print("=== ULokiCMC::StartNewPhysics 0x055C2430 linear 0x80 ===")
for i in CS.disasm(im.read(0x055C2430,0x80),0x055C2430):
    print(f"  {i.address:#010x} {i.bytes.hex():24s} {i.mnemonic} {i.op_str}")
print()
c=CFG(im,0x055C2430)
print(f"CFG: insns={len(c.insns)} calls={len(c.calls)} indirect={len(c.indirect_jumps)} fail={len(c.decode_failures)}")
found=[n for n in c.insns if any(op.type==capstone.x86.X86_OP_MEM and op.mem.disp==0x12b0 for op in c.insns[n].operands)]
print("disp 0x12b0 sites found by CFG:", [hex(x) for x in sorted(found)])
# pdata_union lookup
import csv,os
p=r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv"
print("pdata_union.csv exists:", os.path.exists(p))
if os.path.exists(p):
    hitrows=[]
    with open(p, newline='') as f:
        rd=csv.reader(f)
        hdr=next(rd)
        print("header:", hdr)
        for row in rd:
            try:
                b=int(row[0],0); e=int(row[1],0)
            except Exception:
                continue
            if b <= 0x055C2483 < e or b<=0x055C2430<e:
                hitrows.append(row)
    print("rows covering 0x055C2430 / 0x055C2483:", hitrows)
