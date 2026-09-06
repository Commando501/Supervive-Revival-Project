import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, IMAGEBASE
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=False
def dis(rva, n=40, stop_ret=True):
    out=[]
    code=DATA[rva:rva+n*16]
    for ins in md.disasm(code, rva):
        out.append("0x%07X  %-22s %s"%(ins.address, ins.mnemonic, ins.op_str))
        if len(out)>=n: break
        if stop_ret and ins.mnemonic in ('ret','jmp') and ins.address-rva>4: break
    return "\n".join(out)
if __name__=='__main__':
    for a in sys.argv[1:]:
        r=int(a,16); print("=== 0x%07X"%r); print(dis(r, 45)); print()
