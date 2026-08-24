import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img()
def dump(entry, lo, hi, title):
    c=CFG(im,entry,maxinsn=200000)
    print(f"\n########## {entry:#x} {title} ({len(c.insns)} insns) ##########")
    for a in sorted(x for x in c.insns if lo<=x<=hi):
        print(f"  {c.txt(a):<58} -> {[hex(s) for s in sorted(c.succ.get(a,()))]}")
    return c
dump(0x055c0d30,0,0xFFFFFFFF,"whole fn: 'mov byte [rbx+0x16c8],1'")
dump(0x0559c560,0,0xFFFFFFFF,"whole fn: 'cmp byte [rax+0x16c8],0'")
