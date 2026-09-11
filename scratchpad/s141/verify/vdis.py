import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
import capstone
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail=True
def dis(rva,n=80,stop_ret=True):
    code=im.read(rva,n*16)
    cnt=0
    for i in md.disasm(code, rva):
        rip=i.address+i.size
        extra=''
        # resolve rip-relative
        for op in i.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                t=rip+op.mem.disp
                extra=f"   ; -> {t:#x}"
                try:
                    extra+=f" bytes={im.read(t,8).hex()}"
                except Exception: pass
        print(f"  {i.address:#09x}  {i.bytes.hex():<24s} {i.mnemonic:<8s} {i.op_str}{extra}")
        cnt+=1
        if cnt>=n: break
        if stop_ret and i.mnemonic in ('ret','jmp') and i.mnemonic=='ret': break
if __name__=='__main__':
    rva=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 40
    sr = (len(sys.argv)<=3)
    print(f"=== {rva:#x} page_nonzero={im.page_nonzero(rva)}/4096")
    dis(rva,n,sr)
