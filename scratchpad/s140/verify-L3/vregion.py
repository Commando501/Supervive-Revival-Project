import sys
from vimg import VImg
from vcfg import VCFG
im=VImg()
ENTRY=int(sys.argv[3],16) if len(sys.argv)>3 else 0x035E9EC0
g=VCFG(im,ENTRY)
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
for a in sorted(g.insns):
    if lo<=a<=hi:
        i=g.insns[a]
        succ=g.succ.get(a,[])
        s=("  -> "+",".join(hex(x) for x in succ)) if (len(succ)!=1 or succ[0]!=a+i.size) else ""
        print("0x%08x  %-26s %-8s %-40s%s" % (a," ".join("%02x"%b for b in i.bytes),i.mnemonic,i.op_str,s))
