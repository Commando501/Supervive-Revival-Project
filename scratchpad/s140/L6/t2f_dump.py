import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img()
def dump(entry, lo=None, hi=None, title=""):
    c=CFG(im,entry,maxinsn=200000)
    ks=sorted(c.insns)
    if lo is None: lo,hi=min(ks),max(ks)
    print(f"\n########## {entry:#x} {title}  ({len(ks)} insns, range {min(ks):#x}..{max(ks):#x}) ##########")
    for a in ks:
        if lo<=a<=hi:
            s=[hex(x) for x in sorted(c.succ.get(a,()))]
            print(f"  {c.txt(a):<58} -> {s}")
    return c
dump(0x0530aaa0, title="LokiCMC vtable SLOT 0")
