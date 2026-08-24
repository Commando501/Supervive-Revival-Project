import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def dis(start, end, label=""):
    n = end-start
    b = im.read(start, n)
    print("=== %s  %#x .. %#x (%d bytes) ===" % (label, start, end, n))
    for i in md.disasm(b, start):
        tgt=""
        if i.mnemonic in ('call','jmp') or i.mnemonic.startswith('j'):
            for op in i.operands:
                if op.type == capstone.x86.X86_OP_IMM:
                    tgt = "   -> %#x" % op.imm
        print("%08x  %-24s %-8s %s%s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str, tgt))

if __name__ == '__main__':
    a=int(sys.argv[1],16); b=int(sys.argv[2],16)
    dis(a,b, sys.argv[3] if len(sys.argv)>3 else "")
