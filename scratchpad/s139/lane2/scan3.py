import sys, re; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import DATA, vslots
from grade import extent
import capstone
md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
C=vslots(0x07FBED58,413); L=vslots(0x088F8570,413)
for nm,V in (("CMC",C),("LOKI",L)):
  seen=set()
  for i,a in enumerate(V):
    if a is None or a in seen: continue
    seen.add(a)
    ex=extent(a)
    if not ex: continue
    lo,hi=ex
    if hi-lo>0x3000: continue
    has231=False; jmpreg=False
    for ins in md.disasm(DATA[lo:hi], lo):
        s=ins.mnemonic+' '+ins.op_str
        if '0x231]' in s: has231=True
        if ins.mnemonic=='jmp' and re.fullmatch(r'r[a-z0-9]{2}', ins.op_str): jmpreg=True
    if has231 and jmpreg:
        print("%s slot %3d disp 0x%04X 0x%07X size %d"%(nm,i,i*8,a,hi-lo))
