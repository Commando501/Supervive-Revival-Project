import sys, struct, collections
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img, find_all
import capstone
im = Img('dumps/merged13.dump.exe'); b=im.b
sec=[s for s in im.sections if s[0]=='.text'][0]
lo,hi=sec[1],sec[1]+sec[4]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
DISP=int(sys.argv[1],16) if len(sys.argv)>1 else 0x160
pat=struct.pack('<i',DISP)
cands=find_all(b,pat,lo,hi)
print('raw disp candidates:',len(cands))
out=collections.Counter(); samples=collections.defaultdict(list)
n=0
for pos in cands:
    for back in range(1,13):
        st=pos-back
        if st<lo: continue
        try: ins=next(md.disasm(b[st:st+16], im.rva2va(st)))
        except StopIteration: continue
        if ins.size < back+4: continue
        ok=False
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.disp==DISP and op.mem.index==0:
                ok=True
        if not ok: continue
        # require the disp bytes to be exactly at pos
        key='%s %s'%(ins.mnemonic, ins.op_str)
        # normalize register
        import re
        k=re.sub(r'\b(r[a-z0-9]+|e[a-z]x|e[sd]i|e[bs]p|[a-d][lh]|sil|dil|bpl|spl|r\d+[bwd]?)\b','R',key)
        out[k]+=1
        if len(samples[k])<8: samples[k].append(hex(st))
        n+=1
        break
print('decoded:',n)
for k,v in out.most_common(40):
    print('%6d  %-46s %s'%(v,k,samples[k][:5]))
