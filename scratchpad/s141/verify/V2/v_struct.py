import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,undec,indir = cfg(I, 0x035EC850)
print("ENGINE PhysFalling CFG: insns=%d undecodable=%d indirect=%d" % (len(ins),len(undec),len(indir)))
if undec: print("  undec:", undec[:10])
if indir: print("  indirect jumps:", indir[:10])
rets=[a for a in ins if ins[a].id in RETS]
print("  rets:", [hex(a) for a in sorted(rets)])
lo=min(ins); hi=max(a+ins[a].size for a in ins)
print("  extent %08x..%08x  (span %d bytes)" % (lo,hi,hi-lo))
cov=set()
for a in ins: cov.update(range(a,a+ins[a].size))
print("  covered bytes %d of span %d ; gaps %d" % (len(cov), hi-lo, (hi-lo)-len(cov)))
# gap ranges
gaps=[]; prev=None
for x in range(lo,hi):
    if x not in cov:
        if prev is None: prev=x
    else:
        if prev is not None: gaps.append((prev,x)); prev=None
if prev is not None: gaps.append((prev,hi))
print("  gap ranges:", [(hex(a),hex(b)) for a,b in gaps][:20])
