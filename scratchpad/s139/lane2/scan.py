import sys, re; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, vslots
from grade import extent
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
L=vslots(0x088F8570,413); C=vslots(0x07FBED58,413)
for nm,V in (("CMC",C),("LOKI",L)):
    for i,a in enumerate(V):
        if a is None: continue
        ex=extent(a)
        if not ex: continue
        lo,hi=ex
        if hi-lo>0x4000: hi=lo+0x4000
        txt=[]; has231=False; hasjt=False
        for ins in md.disasm(DATA[lo:hi], lo):
            s=ins.mnemonic+' '+ins.op_str
            if '+ 0x231]' in s: has231=True
            if ins.mnemonic=='jmp' and ('*8' in s or 'qword ptr [' in s): hasjt=True
        if has231 and hasjt:
            print("%s slot %3d disp 0x%04X  0x%07X  size %d"%(nm,i,i*8,a,hi-lo))
