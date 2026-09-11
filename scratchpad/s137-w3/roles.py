import sys, struct, re
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img, find_all
import capstone
im = Img('dumps/merged13.dump.exe'); b=im.b
sec=[s for s in im.sections if s[0]=='.text'][0]
lo,hi=sec[1],sec[1]+sec[4]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
pat=struct.pack('<i',0x160)
res=[]
for pos in find_all(b,pat,lo,hi):
    for back in range(1,13):
        st=pos-back
        if st<lo: continue
        try: ins=next(md.disasm(b[st:st+16], im.rva2va(st)))
        except StopIteration: continue
        if ins.size < back+4: continue
        ok=any(op.type==capstone.x86.X86_OP_MEM and op.mem.disp==0x160 and op.mem.index==0 for op in ins.operands)
        if not ok: continue
        res.append((st,ins.mnemonic,ins.op_str,ins.size))
        break
cmp3=[r for r in res if r[1]=='cmp' and r[2].endswith(', 3') and 'byte' in r[2]]
mvz=[r for r in res if r[1]=='movzx' and 'byte' in r[2]]
print('cmp byte[+0x160],3 :',len(cmp3))
print('movzx byte[+0x160] :',len(mvz))
for r in cmp3:
    print(hex(r[0]))
