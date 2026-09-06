import struct, sys
from capstone import *
from capstone.x86 import *
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read()
pe=struct.unpack_from('<I',D,0x3c)[0]
nsec=struct.unpack_from('<H',D,pe+6)[0]
optoff=pe+0x18
magic=struct.unpack_from('<H',D,optoff)[0]
IMAGEBASE=struct.unpack_from('<Q',D,optoff+0x18)[0]
secs=[]
so=optoff+struct.unpack_from('<H',D,pe+0x14)[0]
for i in range(nsec):
    b=so+i*40
    nm=D[b:b+8].rstrip(b'\0').decode('latin1')
    vs,va,rs,pr=struct.unpack_from('<IIII',D,b+8)
    secs.append((nm,va,vs,pr,rs))
def sec_of(rva):
    for nm,va,vs,pr,rs in secs:
        if va<=rva<va+max(vs,rs): return nm
    return None
FLAT = all(va==pr for nm,va,vs,pr,rs in secs)
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def rd(rva,n): return D[rva:rva+n]
def page_lit(rva):
    p=rva & ~0xFFF
    return sum(1 for b in D[p:p+0x1000] if b)
def dis(rva,n=40):
    out=[]
    for i in md.disasm(D[rva:rva+n*16],rva):
        out.append(i)
        if len(out)>=n: break
    return out
def pr(rva,n=30):
    for i in dis(rva,n):
        print("0x%08X %-24s %s %s"%(i.address,i.bytes.hex(),i.mnemonic,i.op_str))
TERM={'ret','jmp','iret','hlt'}
def cfg(entry,maxins=6000):
    seen={}; stack=[entry]; edges={}
    while stack:
        a=stack.pop()
        if a in seen: continue
        try: ins=next(md.disasm(D[a:a+16],a))
        except StopIteration:
            seen[a]=None; continue
        seen[a]=ins
        m=ins.mnemonic; succ=[]
        if m=='ret' or m.startswith('ret'): pass
        elif m=='jmp':
            op=ins.operands[0]
            if op.type==X86_OP_IMM:
                t=op.imm
                if entry-0x20000 < t < entry+0x20000: succ=[t]
            # indirect / far tail -> terminal
        elif m.startswith('j'):
            succ=[ins.operands[0].imm, ins.address+ins.size]
        elif m in ('int3','ud2','hlt'): pass
        else:
            succ=[ins.address+ins.size]
        edges[a]=succ
        for s in succ:
            if s not in seen: stack.append(s)
        if len(seen)>maxins: break
    return seen,edges
def reach_back(edges,target):
    rev={}
    for a,ss in edges.items():
        for s in ss: rev.setdefault(s,[]).append(a)
    R=set([target]); st=[target]
    while st:
        n=st.pop()
        for p in rev.get(n,[]):
            if p not in R: R.add(p); st.append(p)
    return R,rev
def reach_fwd(edges,start,banned=()):
    R=set(); st=[start]
    while st:
        n=st.pop()
        if n in R or n in banned: continue
        R.add(n)
        for s in edges.get(n,[]): st.append(s)
    return R
def rip(ins):
    for op in ins.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            return ins.address+ins.size+op.mem.disp
    return None
if __name__=='__main__':
    print("FLAT",FLAT,"IMAGEBASE",hex(IMAGEBASE))
    t=sum(1 for nm,va,vs,pr_,rs in secs if nm=='.text')
    for nm,va,vs,p_,rs in secs: print(nm,hex(va),hex(vs),hex(p_),hex(rs))
