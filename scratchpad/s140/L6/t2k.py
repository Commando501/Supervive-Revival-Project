import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); IB=im.imagebase
rd=[s for s in im.sections if s['name']=='.rdata'][0]
RDATA=im.data[rd['praw']:rd['praw']+rd['rawsz']]
LOKI_VT=0x088F8570; ENG_VT=0x07fbed58
def vtpos(entry):
    tb=struct.pack('<Q',IB+entry); out=[]; off=RDATA.find(tb)
    while off!=-1:
        if off%8==0: out.append(rd['va']+off)
        off=RDATA.find(tb,off+1)
    return out
for e,lbl in [(0x0530abea,'the Reset+tailjmp fn'),(0x035d6790,'its tail target'),
              (0x0530ac10,'the flag?snap:Velocity ACCESSOR'),(0x0530aaa0,'ULokiCMC deleting dtor (ctrl)'),
              (0x035d0180,'0x530abab callee'),(0x055ac8e0,'GetLokiCharacterMovement (repo)')]:
    pos=vtpos(e)
    tags=[]
    for p in pos:
        if 0<=p-LOKI_VT<413*8: tags.append(f"LokiCMCvt+{p-LOKI_VT:#x}")
        if 0<=p-ENG_VT<520*8: tags.append(f"EngCMCvt+{p-ENG_VT:#x}")
    print(f"{e:#010x} {lbl:<38} .rdata qword hits={len(pos)} {tags}  first16={im.read(e,16).hex(' ')}")

print("\n--- 0x035d6790 first 40 bytes (is it a destructor?) ---")
for i in CS.disasm(im.read(0x035d6790,0x40),0x035d6790):
    print(f"  {i.address:#010x} {i.bytes.hex(' '):<22} {i.mnemonic} {i.op_str}")

print("\n--- 0x055ac8e0 GetLokiCharacterMovement ---")
for i in CS.disasm(im.read(0x055ac8e0,0x30),0x055ac8e0):
    print(f"  {i.address:#010x} {i.bytes.hex(' '):<22} {i.mnemonic} {i.op_str}")

print("\n--- 0x06e80b10 / 0x06e92ca0 : what band is this? ---")
for e in (0x06e80b10,0x06e92ca0,0x06e92d10):
    print(f"  {e:#x}: {im.read(e,32).hex(' ')}")
    for i in CS.disasm(im.read(e,0x40),e):
        print(f"     {i.address:#010x} {i.mnemonic} {i.op_str}")
    print()
