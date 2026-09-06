import sys, struct
sys.path.insert(0,'scratchpad/s139')
from img import DATA
from capstone import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=False
TEXT_LO,TEXT_HI=0x1000,0x764A000
def callers(target):
    out=[]
    i=TEXT_LO
    while i < TEXT_HI-5:
        # find e8/e9 whose rel32 lands on target
        j=DATA.find(b'\xe8',i,TEXT_HI)
        k=DATA.find(b'\xe9',i,TEXT_HI)
        cands=[x for x in (j,k) if x>=0]
        if not cands: break
        p=min(cands)
        rel=struct.unpack_from('<i',DATA,p+1)[0]
        if p+5+rel==target:
            g=list(md.disasm(DATA[p:p+8],p,1))
            if g and g[0].mnemonic in ('call','jmp') and g[0].size==5:
                out.append((p,g[0].mnemonic))
        i=p+1
    return out
if __name__=="__main__":
    for a in sys.argv[1:]:
        t=int(a,16); c=callers(t)
        print("target 0x%08X : %d direct rel32 call/jmp sites"%(t,len(c)))
        for p,m in c: print("   0x%08X %s"%(p,m))
