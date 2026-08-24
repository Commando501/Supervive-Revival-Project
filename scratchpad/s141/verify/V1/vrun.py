from vimg import VImg
from vcfg import G
im=VImg()
g=G(im,0x035EC850)
addrs=sorted(g.I)
lo,hi=addrs[0],addrs[-1]+g.I[addrs[-1]].size
cov=sum(g.I[a].size for a in addrs)
span=hi-lo
rets=[a for a in addrs if g.I[a].mnemonic in ('ret','retf')]
direct=sum(1 for v in g.calls.values() if v is not None)
print(f"entry 0x035EC850")
print(f"  instructions        {len(g.I)}")
print(f"  calls               {len(g.calls)}  (direct {direct}, indirect {len(g.calls)-direct})")
print(f"  indirect jumps      {len(g.ijmp)}")
print(f"  decode failures     {len(g.fail)}")
print(f"  ret instructions    {len(rets)}  at {[hex(r) for r in rets]}")
print(f"  addr range          {lo:#x}..{hi:#x}  span={span}")
print(f"  decoded bytes       {cov}   coverage={cov/span*100:.2f}%  gap bytes={span-cov}")
# backward edges
bk=[(s,d) for s in g.succ for d in g.succ[s] if d<=s]
print(f"  backward edges      {len(bk)}: {[(hex(s),hex(d)) for s,d in bk]}")
