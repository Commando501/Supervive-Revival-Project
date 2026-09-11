import sys, numpy as np
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import md, fmt
from capstone.x86 import *
img=L2Img('dumps/merged14.dump.exe'); buf=img.buf
t=img.sect_of(0x1000); lo=t['va']; hi=t['va']+t['vsize']
d=np.frombuffer(buf[lo:hi],dtype=np.uint8); n=len(d)
v=(d[0:n-3].astype(np.uint32)|(d[1:n-2].astype(np.uint32)<<8)
   |(d[2:n-1].astype(np.uint32)<<16)|(d[3:n].astype(np.uint32)<<24))
key=v+np.arange(len(v),dtype=np.uint32)
m=md()
print("=== Q1 tail (CORRECTED validator: LONGEST decode wins, so SSE prefixes are not stripped) ===")
for tgt in (0x077F5180, 0x077F5188):
    want=np.uint32((tgt-lo-4)&0xFFFFFFFF)
    hits=(np.nonzero(key==want)[0]+lo).tolist()
    out=[]
    for h in hits:
        cands=[]
        for back in range(1,14):
            st=h-back
            try: g=list(m.disasm(img.read(st,16), st, count=1))
            except Exception: g=[]
            if not g: continue
            i=g[0]
            if st+i.size != h+4: continue
            if any(op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP and
                   i.address+i.size+op.mem.disp==tgt for op in i.operands):
                cands.append(i)
        if cands:
            longest=max(cands,key=lambda x:x.size)
            sizes=[c.size for c in cands]
            out.append((longest,cands))
    print("\n-- 0x%08X : %d raw candidates -> %d with a valid rip-rel decode --" % (tgt,len(hits),len(out)))
    for longest,cands in out:
        memsz=[op.size for op in longest.operands if op.type==X86_OP_MEM]
        alias='' if len(cands)==1 else "   (%d overlapping decodes; shorter alias(es): %s)" % (
            len(cands), ', '.join('%s/%dB'%(c.mnemonic,c.size) for c in cands if c is not longest))
        print("   %s   READS %d BYTES%s" % (fmt(longest), memsz[0] if memsz else -1, alias))
