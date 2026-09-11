import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data
sec=[s for s in im.sections if s['name']=='.text'][0]
base=sec['va']; size=max(sec['vsz'],sec['rawsz']); data=d[sec['praw']:sec['praw']+size]
def rel32_callers(target):
    out=[]
    for i in range(0, size-5):
        if data[i]!=0xE8: continue
        rel=struct.unpack_from('<i',data,i+1)[0]
        if base+i+5+rel == target: out.append(base+i)
    return out
for t in (0x055A56B0,):
    c=rel32_callers(t); print(f"rel32 callers of {t:#x}: {[hex(x) for x in c]}  (FLOOR)")
print()
print("--- C's Super 0x035DB4A0 first 0x70 ---")
for i in CS.disasm(im.read(0x035DB4A0,0x70),0x035DB4A0):
    print(f"  {i.address:#010x} {i.mnemonic} {i.op_str}")
