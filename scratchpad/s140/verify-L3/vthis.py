# INDEPENDENT must-analysis 'this' tracker. Written from scratch.
# Lattice value: None (unknown) | ('this', disp) | ('frame', disp)
import capstone
from capstone import CS_AC_WRITE, CS_AC_READ
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS

R64 = {}
def base64(reg):
    # map any sub-register to its 64-bit parent name
    n = CS.reg_name(reg)
    if n is None: return None
    return n

# build full sub-register -> parent map using capstone reg names
PARENT = {}
for p, kids in {
 'rax':['eax','ax','al','ah'],'rbx':['ebx','bx','bl','bh'],'rcx':['ecx','cx','cl','ch'],
 'rdx':['edx','dx','dl','dh'],'rsi':['esi','si','sil'],'rdi':['edi','di','dil'],
 'rbp':['ebp','bp','bpl'],'rsp':['esp','sp','spl'],
 **{('r%d'%i):['r%dd'%i,'r%dw'%i,'r%db'%i] for i in range(8,16)}
}.items():
    PARENT[p]=p
    for k in kids: PARENT[k]=p

def parent(name):
    return PARENT.get(name)

VOLATILE = ['rax','rcx','rdx','r8','r9','r10','r11']
GPRS = ['rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp'] + ['r%d'%i for i in range(8,16)]

def transfer(ins, st):
    st = dict(st)
    m = ins.mnemonic
    ops = ins.operands
    # calls kill volatile + all xmm (we don't track xmm)
    if m == 'call':
        for r in VOLATILE: st[r] = None
        return st
    # lea reg, [base + disp]
    if m == 'lea' and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_MEM:
        d = ops[0]; s = ops[1].mem
        dn = parent(CS.reg_name(d.reg))
        if dn is None: return st
        if s.index == 0 and s.base != 0:
            bn = parent(CS.reg_name(s.base))
            bv = st.get(bn)
            if bv is not None:
                st[dn] = (bv[0], bv[1] + s.disp)
            else:
                st[dn] = None
        else:
            st[dn] = None
        return st
    # mov reg, reg  (64-bit only establishes)
    if m == 'mov' and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_REG:
        d=ops[0]; s=ops[1]
        dn=parent(CS.reg_name(d.reg)); sn=parent(CS.reg_name(s.reg))
        if dn is None: return st
        if d.size==8 and s.size==8:
            st[dn]=st.get(sn)
        else:
            st[dn]=None
        return st
    # any other write to a register operand kills it
    for o in ops:
        if o.type==X86_OP_REG and (o.access & CS_AC_WRITE):
            pn=parent(CS.reg_name(o.reg))
            if pn: st[pn]=None
    # also implicit writes
    for r in ins.regs_write:
        pn=parent(CS.reg_name(r))
        if pn and pn in GPRS: st[pn]=None
    return st

def analyse(g, entry_state):
    IN={}; OUT={}
    order=sorted(g.insns)
    IN[g.entry]=dict(entry_state)
    work=[g.entry]
    inq={g.entry}
    # iterate to fixpoint with worklist; join = intersection (must)
    while work:
        a=work.pop()
        inq.discard(a)
        st=IN.get(a)
        if st is None: continue
        o=transfer(g.insns[a], st)
        if OUT.get(a)!=o:
            OUT[a]=o
        for s in g.succ.get(a,[]):
            if s not in g.insns: continue
            cur=IN.get(s)
            if cur is None:
                new=dict(o)
            else:
                new={}
                for k in set(cur)|set(o):
                    if cur.get(k) is not None and cur.get(k)==o.get(k):
                        new[k]=cur[k]
                    else:
                        new[k]=None
            if new!=cur:
                IN[s]=new
                if s not in inq:
                    work.append(s); inq.add(s)
    return IN, OUT

if __name__=='__main__':
    im=VImg(); g=VCFG(im,0x035E9EC0)
    entry={r:None for r in GPRS}
    entry['rcx']=('this',0)
    entry['rsp']=('frame',0)
    IN,OUT=analyse(g,entry)
    print("analysed nodes with IN state: %d / %d" % (len([a for a in g.insns if a in IN]), len(g.insns)))
    def show(a,regs,label):
        st=IN.get(a)
        if st is None: print("  0x%08x %-42s  <no IN state>"%(a,label)); return
        ins=g.insns[a]
        vals=", ".join("%s=%s"%(r, st.get(r)) for r in regs)
        print("  0x%08x %-42s  %s" % (a, "%s %s"%(ins.mnemonic,ins.op_str), vals))
    print("\n--- CALIBRATION / CONTROLS (my own tracker) ---")
    for a,regs,lab in [
        (0x035e9eee,['rcx'],'P0'),
        (0x035e9f14,['rbx'],'P1'),
        (0x035e9f17,['rcx'],'P2'),
        (0x035e9f35,['rcx'],'N1 must be None'),
        (0x035e9fb5,['rcx'],'N2 must be None'),
        (0x035e9ef5,['r13'],'N3 must be None'),
        (0x035e9f82,['rbx'],'CALIB-a'),
        (0x035eb130,['rbx','r15'],'CALIB-b'),
        (0x035eb785,['rdi','r14','rsi'],'N4'),
        (0x035eb78d,['rbx'],'LastUpdateLocation store'),
        (0x035eb798,['rbx'],'LastUpdateRotation store'),
        (0x035eb77d,['rbx'],'ServerLastTransformUpdateTimeStamp store'),
        (0x035ea009,['rbx'],'bForceNextFloorCheck store'),
    ]:
        show(a,regs,lab)
