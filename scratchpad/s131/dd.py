"""dd.py <rva> [n] [--dump path] : disassemble with RVA-resolved targets."""
import sys
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
DEF = r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
a = sys.argv[1:]
dump = DEF
if "--dump" in a:
    k=a.index("--dump"); dump=a[k+1]; del a[k:k+2]
img = fkdis.Img(dump); IB = img.imagebase
rva = int(a[0],0); n = int(a[1],0) if len(a)>1 else 0x80
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
data = img.read(rva,n)
for p,z in fkdis.zero_pages(img,rva,n):
    if z: print(";; WARNING page 0x%08X ALL-ZERO (not decrypted)"%p)
for ins in md.disasm(data, IB+rva):
    r = ins.address-IB
    ann=""
    for op in ins.operands:
        if op.type==2 and (ins.mnemonic=="call" or ins.mnemonic[0]=="j"):
            t=op.imm-IB; s=img.sec_of(t)
            ann="   ; -> RVA 0x%08X [%s]"%(t, s[0] if s else "?")
        if op.type==3 and op.mem.base==41:
            t=(ins.address+ins.size+op.mem.disp)-IB; s=img.sec_of(t)
            ann="   ; -> RVA 0x%08X [%s]"%(t, s[0] if s else "?")
    print("  0x%08X  %-22s %s %s%s"%(r, ins.bytes.hex(), ins.mnemonic, ins.op_str, ann))
