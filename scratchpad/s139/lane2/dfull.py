import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA
from grade import extent
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
r=int(sys.argv[1],16)
ex=extent(r); 
if ex: lo,hi=ex
else: lo,hi=r,r+int(sys.argv[2],16) if len(sys.argv)>2 else r+0x200
print("# 0x%07X extent 0x%07X..0x%07X (%d B)"%(r,lo,hi,hi-lo))
for ins in md.disasm(DATA[lo:hi], lo):
    print('0x%07X  %-9s %s'%(ins.address, ins.mnemonic, ins.op_str))
