import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, vslots
from grade import extent
import capstone, re
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
C=vslots(0x07FBED58,413)
for i,a in enumerate(C):
    if a is None: continue
    ex=extent(a)
    if not ex: continue
    lo,hi=ex
    if hi-lo>0x6000: hi=lo+0x6000
    n231=0; vcalls=[]
    for ins in md.disasm(DATA[lo:hi], lo):
        s=ins.mnemonic+' '+ins.op_str
        if '0x231]' in s: n231+=1
        if ins.mnemonic=='call':
            m=re.match(r'qword ptr \[\w+ \+ (0x[0-9a-f]+)\]$', ins.op_str)
            if m: vcalls.append(int(m.group(1),16))
    if n231>=1:
        print("CMC slot %3d disp 0x%04X 0x%07X size %5d  n231=%d  vcalls=%s"%(i,i*8,a,hi-lo,n231,sorted(set(hex(v) for v in vcalls))))
