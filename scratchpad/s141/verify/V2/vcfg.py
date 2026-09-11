# V2 independent sound recursive-descent CFG. Writes classified from operands[0].type==MEM.
import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg
from capstone import *
from capstone.x86 import *

md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True

UNCOND  = {X86_INS_JMP}
RETS    = {X86_INS_RET, X86_INS_RETF, X86_INS_IRET}
COND    = {X86_INS_JA,X86_INS_JAE,X86_INS_JB,X86_INS_JBE,X86_INS_JCXZ,X86_INS_JECXZ,X86_INS_JRCXZ,
           X86_INS_JE,X86_INS_JG,X86_INS_JGE,X86_INS_JL,X86_INS_JLE,X86_INS_JNE,X86_INS_JNO,
           X86_INS_JNP,X86_INS_JNS,X86_INS_JO,X86_INS_JP,X86_INS_JS,X86_INS_LOOP,X86_INS_LOOPE,X86_INS_LOOPNE}

def cfg(img, entry, limit=200000):
    """returns insns{addr:CsInsn}, succ{addr:set}, undecodable[], indirect[]"""
    insns={}; succ={}; undec=[]; indir=[]
    stack=[entry]; seen=set()
    while stack:
        a=stack.pop()
        if a in seen: continue
        seen.add(a)
        try: b = img.read(a, 24)
        except KeyError:
            undec.append((a,'unmapped')); continue
        lst = list(md.disasm(b, a))
        if not lst:
            undec.append((a,'decode-fail')); continue
        ins = lst[0]
        insns[a]=ins
        nxt = a+ins.size
        s=set()
        gid = ins.id
        if gid in RETS:
            pass
        elif gid == X86_INS_INT3 or ins.mnemonic=='ud2':
            pass
        elif gid in UNCOND:
            op=ins.operands[0]
            if op.type==X86_OP_IMM: s.add(op.imm)
            else: indir.append((a,ins.op_str))
        elif gid in COND:
            op=ins.operands[0]
            if op.type==X86_OP_IMM: s.add(op.imm)
            else: indir.append((a,ins.op_str))
            s.add(nxt)
        else:
            s.add(nxt)
        succ[a]=s
        for t in s:
            if t not in seen: stack.append(t)
        if len(insns)>limit: raise RuntimeError("limit")
    return insns, succ, undec, indir

def preds(succ):
    p={}
    for a,ss in succ.items():
        for t in ss: p.setdefault(t,set()).add(a)
    return p

def reach(succ, entry, removed=frozenset()):
    if entry in removed: return set()
    r=set([entry]); st=[entry]
    while st:
        a=st.pop()
        for t in succ.get(a,()):
            if t in removed or t in r: continue
            r.add(t); st.append(t)
    return r

def mem_writes(ins):
    """True if operands[0] is a MEM destination (never uses regs_access)."""
    if not ins.operands: return None
    o=ins.operands[0]
    if o.type!=X86_OP_MEM: return None
    # exclude pure-compare/test/push forms
    if ins.id in (X86_INS_CMP,X86_INS_TEST,X86_INS_PUSH,X86_INS_LEA): return None
    if ins.mnemonic.startswith('cmp') or ins.mnemonic.startswith('ucomis') or ins.mnemonic.startswith('comis'): return None
    return o
