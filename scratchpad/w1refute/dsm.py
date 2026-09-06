import sys; sys.path.insert(0,'scratchpad/w1refute')
from pe import Img
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
im=Img(sys.argv[1]); s=int(sys.argv[2],16); e=int(sys.argv[3],16)
for i in md.disasm(im.read(s,e-s),s):
    print("0x%08X  %-24s %s %s"%(i.address,i.bytes.hex(' '),i.mnemonic,i.op_str))
