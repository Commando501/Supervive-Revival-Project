import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
from capstone import *
from capstone.x86 import *

pe = load()
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def dis(start, end, label=''):
    print("=== %s  0x%07X .. 0x%07X (%d bytes) ===" % (label, start, end, end-start))
    code = pe.read(start, end-start)
    n=0
    for ins in md.disasm(code, start):
        n+=1
        print("0x%07x  %-24s %-8s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
    print("  [decoded %d instructions]" % n)

if __name__ == '__main__':
    a=int(sys.argv[1],16); b=int(sys.argv[2],16)
    lbl = sys.argv[3] if len(sys.argv)>3 else ''
    dis(a,b,lbl)
