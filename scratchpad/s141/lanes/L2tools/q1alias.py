import sys, struct
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import cfg, fmt
img=L2Img('dumps/merged14.dump.exe')
# Is .pdata usable in this image?
s=img.sect_of(0x0A0B7000)
d=img.read(s['va'], 0x1000)
print(".pdata first 64 bytes:", d[:64].hex())
nz=sum(1 for c in d if c)
print(".pdata first page nonzero: %d/4096" % nz)
# find the RUNTIME_FUNCTION covering 0x035E428C
rows=[]
raw=img.read(s['va'], s['rsize'])
import array
n=len(raw)//12
best=None
for k in range(n):
    b,e,u = struct.unpack_from('<III', raw, k*12)
    if b==0 and e==0: continue
    if b <= 0x035E428C < e and e-b>1:
        best=(b,e,u); break
print("RUNTIME_FUNCTION covering 0x035E428C:", ("0x%08X..0x%08X"%(best[0],best[1])) if best else "NONE")
if best:
    insns,succ,bad = cfg(img, best[0], best[0]-0x10, best[1]+0x10)
    print("  CFG from 0x%08X: %d insns, %d undecodable" % (best[0], len(insns), len(bad)))
    for a in (0x035E428C,0x035E4298,0x035E43A3,0x035E43BB):
        print("   is 0x%08X a real instruction boundary in the sound CFG? %s" % (a, a in insns))
    # show what IS at those addresses per the sound CFG
    for a in sorted(insns):
        if 0x035E4280 <= a <= 0x035E42A5: print("      "+fmt(insns[a]))
