import sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
im=Img(); c=CFG(im,0x035E9EC0)
X=capstone.x86
print("=== ALL indirect calls with disp 0x720 ===")
for r,t in sorted(c.calls.items()):
    i=c.insns[r]
    if t is None and '0x720' in i.op_str:
        print(f"  {r:#010x} {i.mnemonic} {i.op_str}")
print("=== ALL indirect calls with disp 0x6b8 (HasValidData) ===")
for r,t in sorted(c.calls.items()):
    i=c.insns[r]
    if t is None and '0x6b8' in i.op_str:
        print(f"  {r:#010x} {i.mnemonic} {i.op_str}")
print("=== count of all calls, direct vs indirect ===")
d=sum(1 for t in c.calls.values() if t is not None); print(" direct",d,"indirect",len(c.calls)-d)
