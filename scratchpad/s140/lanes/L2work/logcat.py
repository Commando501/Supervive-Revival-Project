import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
X=capstone.x86
im=Img(); BASE=im.imagebase
def astr(rva,n=64):
    b=im.read(rva,n); out=[]
    for x in b:
        if x==0: break
        out.append(chr(x) if 32<=x<127 else '?')
    return ''.join(out)
print("record +0x18 targets read as ASCII (.data -- MERGED IMAGE, flagged):")
for r in (0x09f86387,0x09f863a4):
    print(f"   {r:#010x} {im.read(r,32).hex()}  A={astr(r)!r}")
print()
print("=== engine StartNewPhysics 0x03600990 first 0x120 bytes ===")
for i in CS.disasm(im.read(0x03600990,0x120),0x03600990):
    extra=''
    for op in i.operands:
        if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
            t=i.address+i.size+op.mem.disp; s=im.sec_of(t)
            extra=f"   ; -> {t:#010x} [{s['name'] if s else '?'}]"
    print(f"  {i.address:#010x} {i.bytes.hex():<22s} {i.mnemonic} {i.op_str}{extra}")
