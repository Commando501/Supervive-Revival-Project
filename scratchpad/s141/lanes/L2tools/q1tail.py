import sys, struct, numpy as np
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import md, fmt
from capstone.x86 import *
img=L2Img('dumps/merged14.dump.exe'); buf=img.buf
t=img.sect_of(0x1000); lo=t['va']; hi=t['va']+t['vsize']
d=np.frombuffer(buf[lo:hi], dtype=np.uint8)
n=len(d)
# unaligned int32 at every offset
v = (d[0:n-3].astype(np.uint32)
     | (d[1:n-2].astype(np.uint32)<<8)
     | (d[2:n-1].astype(np.uint32)<<16)
     | (d[3:n  ].astype(np.uint32)<<24))
offs = np.arange(len(v), dtype=np.uint32)
key = v + offs      # wraps mod 2^32 naturally
m=md()
print("=== Q1 tail: references to the gate constant and its neighbour (rip-rel disp32, validated by decode) ===")
for tgt in (0x077F5180, 0x077F5188, 0x076B498C, 0x076A10E0):
    want = np.uint32((tgt - lo - 4) & 0xFFFFFFFF)
    hits = (np.nonzero(key == want)[0] + lo).tolist()
    real=[]
    for h in hits:
        for back in range(1,12):
            st=h-back
            try: g=list(m.disasm(img.read(st,16), st, count=1))
            except Exception: g=[]
            if not g: continue
            i=g[0]
            if st+i.size != h+4: continue
            if any(op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP and
                   i.address+i.size+op.mem.disp==tgt for op in i.operands):
                real.append(i); break
    print("\n-- 0x%08X : %d raw candidates -> %d validated rip-rel instructions --" % (tgt,len(hits),len(real)))
    for i in real[:30]: print("   " + fmt(i))
    if not real: print("   (NONE validated -> no decrypted code references it)")
