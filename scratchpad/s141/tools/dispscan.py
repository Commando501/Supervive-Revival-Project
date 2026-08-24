import sys, struct, collections
sys.path.insert(0,'.')
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); data=im.data
sec={s['name']:s for s in im.sections}; TX=sec['.text']
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
disp = int(sys.argv[1],16)
lo = int(sys.argv[2],16) if len(sys.argv)>2 else TX['va']
hi = int(sys.argv[3],16) if len(sys.argv)>3 else TX['va']+TX['vsz']
pat = struct.pack('<i', disp)
buf = data[TX['praw']:TX['praw']+TX['vsz']]
res=[]
i = lo-TX['va']
end = hi-TX['va']
while True:
    j = buf.find(pat, i, end)
    if j<0: break
    # try decoding starting 1..12 bytes before
    va = TX['va']+j
    found=False
    for back in range(3,13):
        s = va-back
        try: b = im.read(s, 16)
        except ValueError: continue
        g = CS.disasm(b, s)
        try: ins = next(g)
        except StopIteration: continue
        if ins.address+ins.size <= va+4 and ins.address+ins.size >= va+4:
            for op in ins.operands:
                if op.type == capstone.x86.X86_OP_MEM and op.mem.disp == disp and op.mem.base != 0:
                    res.append((s, ins.mnemonic+' '+ins.op_str)); found=True; break
        if found: break
    i = j+1
print(f"disp {disp:#x}: {len(res)} decoded memory operands in [{lo:#x},{hi:#x})")
for a,t in res: print(f"  {a:#010x}  {t}")
