import sys, struct; sys.path.insert(0,'scratchpad/s132')
from uht import img
import capstone
def dis(im, start, end, filt=None):
    d = im.read(start, end-start)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
    out=[]
    for i in md.disasm(d, im.imagebase+start):
        rva = i.address - im.imagebase
        line = f"  0x{rva:07X}  {i.bytes.hex():<22s} {i.mnemonic} {i.op_str}"
        if filt is None or filt(i, line): out.append(line)
    return out
if __name__=="__main__":
    im=img(sys.argv[3] if len(sys.argv)>3 else "merged4")
    print("\n".join(dis(im, int(sys.argv[1],0), int(sys.argv[2],0))))
