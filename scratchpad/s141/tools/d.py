import sys
sys.path.insert(0,'.')
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
def dis(rva, n=40, stop=True):
    b = im.read(rva, min(4096, n*16))
    out=[]
    for i in CS.disasm(b, rva):
        s=f"{i.address:#010x}  {i.bytes.hex():<20s} {i.mnemonic} {i.op_str}"
        out.append(s)
        if stop and i.mnemonic in ('ret','jmp') and len(out)>0: break
        if len(out)>=n: break
    return out
if __name__=='__main__':
    n = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 30
    args = [a for a in sys.argv[1:] if not a.isdigit()]
    for a in args:
        r=int(a,16)
        print(f"=== {r:#x}  page_nonzero={im.page_nonzero(r)}/4096")
        for l in dis(r,n): print("  "+l)
