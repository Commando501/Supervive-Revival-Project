# Find the REAL containing function of an address: walk back through entry candidates
# and take the first (nearest, then progressively earlier) whose recursive-descent CFG
# actually COVERS the target address. Also report frame size and base-register definition.
import sys, os, bisect
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
import funcres
from cfg import walk
import capstone as CS
from capstone import x86 as X86
pe=load()
md=CS.Cs(CS.CS_ARCH_X86,CS.CS_MODE_64); md.detail=True

def real_entry(addr, tries=60, limit=0x8000):
    E,_ = funcres.build()
    i = bisect.bisect_right(E, addr)-1
    best=None
    n=0
    while i>=0 and n<tries:
        e=E[i]
        if addr-e > limit: break
        try:
            insns,edges,fails = walk(e, limit=limit)
        except Exception:
            i-=1; n+=1; continue
        if addr in insns:
            best=(e,insns,edges)
        i-=1; n+=1
    return best  # the EARLIEST covering entry found

def frame_and_defs(entry, insns, target, basename):
    """frame alloc + all definitions of `basename` reachable in the function"""
    fs=0; defs=[]
    for a in sorted(insns):
        i=insns[a]
        if i.mnemonic=='sub' and i.operands and i.operands[0].type==X86.X86_OP_REG \
           and i.reg_name(i.operands[0].reg)=='rsp' and i.operands[1].type==X86.X86_OP_IMM:
            fs=max(fs,i.operands[1].imm)
        if i.operands and i.operands[0].type==X86.X86_OP_REG:
            rn=i.reg_name(i.operands[0].reg)
            if rn==basename and i.mnemonic not in ('cmp','test'):
                defs.append((a,i.mnemonic,i.op_str,i.bytes.hex()))
    return fs, defs
