import sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img(); c=CFG(im,0x035E9EC0)
lo=int(sys.argv[1],16); n=int(sys.argv[2])
cnt=0
for r in sorted(c.insns):
    if r>=lo:
        i=c.insns[r]
        print(f"{r:#010x}  {i.bytes.hex():<26s} {i.mnemonic} {i.op_str}")
        cnt+=1
        if cnt>=n: break
