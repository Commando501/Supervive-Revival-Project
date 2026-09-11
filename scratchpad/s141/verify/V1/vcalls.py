from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
import collections
d=collections.Counter()
for a,t in sorted(g.calls.items()):
    if t is not None: d[t]+=1
for t,c in sorted(d.items()):
    print(f"  target {t:#010x} x{c}  page={im.pnz(t)}/4096  first16={im.read(t,16).hex()}")
print(f"  distinct direct targets: {len(d)}, total direct calls {sum(d.values())}")
print()
print("=== indirect calls by displacement ===")
e=collections.Counter()
for a,t in sorted(g.calls.items()):
    if t is None:
        e[g.I[a].op_str]+=1
for k,c in sorted(e.items(), key=lambda x:-x[1]):
    print(f"   {k:34s} x{c}")
