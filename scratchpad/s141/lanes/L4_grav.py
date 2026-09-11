import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
BASE=im.imagebase
def slot(vt,disp): 
    va=struct.unpack_from('<Q',im.read(vt+disp,8))[0]; return va-BASE if va else 0
def dis(rva,n,label):
    print("=== %s @ %#x ===" % (label,rva))
    for i in md.disasm(im.read(rva,n), rva):
        t=""
        if i.mnemonic=='call' or i.mnemonic.startswith('j'):
            for op in i.operands:
                if op.type==capstone.x86.X86_OP_IMM: t="  -> %#x"%op.imm
        # resolve rip-relative
        rip=""
        for op in i.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                tgt=i.address+i.size+op.mem.disp
                rip="  [rip-> %#x]"%tgt
                try:
                    raw=im.read(tgt,8)
                    rip += " f32=%r f64=%r" % (struct.unpack('<f',raw[:4])[0], struct.unpack('<d',raw)[0])
                except Exception: pass
        print("%08x  %-22s %-8s %s%s%s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,t,rip))
    print()
ENG_VT=0x07FBED58; LOKI_VT=0x088F8570
print("engine CMC disp 0x4C0 (GetGravityZ) -> %#x" % slot(ENG_VT,0x4C0))
print("loki   CMC disp 0x4C0              -> %#x" % slot(LOKI_VT,0x4C0))
print()
dis(slot(ENG_VT,0x4C0), 96, "ENGINE UCharacterMovementComponent::GetGravityZ (vt disp 0x4C0)")
dis(0x055AB8C0, 128, "ULokiCMC::GetGravityZ 0x055AB8C0")
