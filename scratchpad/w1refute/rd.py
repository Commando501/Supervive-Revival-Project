import sys,struct
sys.path.insert(0,'scratchpad/w1refute')
from pe import Img
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def rd(img,start,limit=0x4000):
    seen={}; stack=[start]; calls=set(); mn=start; mx=start
    while stack:
        a=stack.pop()
        while True:
            if a in seen: break
            code=img.read(a,16)
            ins=list(md.disasm(code,a))
            if not ins: seen[a]=('(bad)','',1); break
            i=ins[0]
            seen[a]=(i.mnemonic,i.op_str,i.size)
            mn=min(mn,a); mx=max(mx,a+i.size)
            m=i.mnemonic
            if m=='call':
                op=i.operands[0]
                if op.type==X86_OP_IMM: calls.add(op.imm)
                a=a+i.size; continue
            if m in ('jmp',):
                op=i.operands[0]
                if op.type==X86_OP_IMM:
                    t=op.imm
                    if abs(t-start)<limit: a=t; continue
                    else: calls.add(('tailjmp',t)); break
                break
            if m.startswith('j'):
                op=i.operands[0]
                if op.type==X86_OP_IMM:
                    t=op.imm
                    if abs(t-start)<limit: stack.append(t)
                a=a+i.size; continue
            if m in ('ret','retf','int3','ud2'): break
            a=a+i.size
    return seen,calls,mn,mx
if __name__=='__main__':
    img=Img(sys.argv[1]); start=int(sys.argv[2],16)
    seen,calls,mn,mx=rd(img,start)
    addrs=sorted(seen)
    print("start 0x%X n_ins=%d min=0x%X max_end=0x%X span=%d"%(start,len(seen),mn,mx,mx-mn))
    # gaps
    gaps=[]
    prev=None
    for a in addrs:
        if prev is not None and a!=prev: gaps.append((prev,a))
        prev=a+seen[a][2]
    for g in gaps: print("GAP 0x%X..0x%X (%d bytes)"%(g[0],g[1],g[1]-g[0]))
    rets=[a for a in addrs if seen[a][0] in('ret','retf')]
    print("rets:", ["0x%X"%a for a in rets])
    print("ncalls distinct:",len([c for c in calls if isinstance(c,int)]))
    for c in sorted([c for c in calls if isinstance(c,int)]): print("  call 0x%X"%c)
    for c in calls:
        if not isinstance(c,int): print("  TAILJMP 0x%X"%c[1])
