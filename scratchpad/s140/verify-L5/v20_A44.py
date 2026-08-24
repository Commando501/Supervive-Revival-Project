import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img()
c=CFG(im,0x055B8370)
ex,R=c.exits_from(0x055B840C)
print("The 44 instructions that can reach the accumulate:")
for n in sorted(R):
    print("  ",c.txt(n))
print()
print("calls inside R:", [(hex(k),hex(v) if v else 'INDIRECT') for k,v in sorted(c.calls.items()) if k in R])
