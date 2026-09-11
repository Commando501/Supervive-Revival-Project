# L1 independent recursive-descent CFG. Written from scratch.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
import capstone as CS
from capstone import x86 as X86

pe = load()
md = CS.Cs(CS.CS_ARCH_X86, CS.CS_MODE_64)
md.detail = True

UNCOND = {'jmp'}
COND = {'je','jne','jz','jnz','ja','jae','jb','jbe','jg','jge','jl','jle','jo','jno',
        'js','jns','jp','jnp','jpe','jpo','jcxz','jecxz','jrcxz','loop','loope','loopne'}
TERM  = {'ret','retf','iret','iretd','iretq','ud2','hlt'}

def walk(entry, limit=0x20000):
    """Recursive descent. Returns dict addr->insn, plus edges."""
    insns = {}
    edges = {}   # addr -> list of (target, kind)
    todo = [entry]
    fails = []
    while todo:
        a = todo.pop()
        if a in insns: continue
        if a < entry or a > entry+limit: continue
        code = pe.read(a, 32)
        got = list(md.disasm(code, a, count=1))
        if not got:
            fails.append(a); continue
        ins = got[0]
        insns[a] = ins
        m = ins.mnemonic
        nxt = a + ins.size
        succ = []
        if m in TERM:
            pass
        elif m in UNCOND:
            op = ins.operands[0]
            if op.type == X86.X86_OP_IMM:
                succ.append((op.imm, 'jmp'))
            else:
                succ.append((None, 'indirect_jmp'))
        elif m in COND:
            op = ins.operands[0]
            if op.type == X86.X86_OP_IMM:
                succ.append((op.imm, 'jcc'))
            else:
                succ.append((None, 'indirect_jcc'))
            succ.append((nxt, 'fall'))
        elif m == 'call':
            succ.append((nxt, 'fall'))   # calls return (checked separately)
        else:
            succ.append((nxt, 'fall'))
        edges[a] = succ
        for t,k in succ:
            if t is not None:
                todo.append(t)
    return insns, edges, fails

def call_targets(insns):
    out = {}
    for a,ins in insns.items():
        if ins.mnemonic == 'call':
            op = ins.operands[0]
            if op.type == X86.X86_OP_IMM: out[a] = ('direct', op.imm)
            elif op.type == X86.X86_OP_MEM:
                out[a] = ('indirect_mem', ins.op_str)
            else: out[a] = ('indirect_reg', ins.op_str)
    return out

def preds_of(edges, target):
    """every instruction with an edge INTO target"""
    out = []
    for a, succ in edges.items():
        for t,k in succ:
            if t == target: out.append((a,k))
    return out

def reach_backward(edges, insns, target):
    """set of instrs that can reach target, following successor edges backwards.
       calls' fallthrough counted (they return)."""
    rev = {}
    for a,succ in edges.items():
        for t,k in succ:
            if t is None: continue
            rev.setdefault(t, []).append(a)
    seen=set([target]); todo=[target]
    while todo:
        n = todo.pop()
        for p in rev.get(n, []):
            if p not in seen:
                seen.add(p); todo.append(p)
    return seen

def forward(edges, start, banned=frozenset()):
    seen=set(); todo=[start]
    while todo:
        n=todo.pop()
        if n in seen or n in banned: continue
        seen.add(n)
        for t,k in edges.get(n,[]):
            if t is not None: todo.append(t)
    return seen
