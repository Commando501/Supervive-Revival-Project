"""L3 final v2. Fixes a defect found in v1: reporting a branch direction as
"forced" whenever exactly one successor was in dom(S). That is WRONG at a JOIN
point -- `je L` where both arms converge at L makes L a dominator of S while the
fallthrough is not, and v1 printed "TAKEN" for a branch that constrains nothing.

Correct test: branch B constrains S iff B in dom(S) AND exactly one successor of
B can REACH S. Then that direction is forced.

Also computes post-dominance so we can say which stores are on EVERY path from a
point to the single `ret`.
"""
import sys, collections
sys.path.insert(0, '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG
from thistrack import analyse, mem_this_off
from l3_stores import dominators

ENTRY = 0x035E9EC0
CALL  = 0x035EB13A
RET   = 0x035EB1CA
AC_W  = capstone.CS_AC_WRITE
FORCE_STORE = {'movups','movdqu','movnps','movntps','movntdq'}
COND = {'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}

def is_store(i):
    if not i.operands: return None
    o = i.operands[0]
    if o.type != X.X86_OP_MEM: return None
    if (o.access & AC_W) or i.mnemonic in FORCE_STORE: return o
    return None

def build_reach(c):
    """forward reach sets, memoised via reverse topological-ish iteration"""
    reach = {}
    def go(n, stack):
        if n in reach: return reach[n]
        S = {n}
        for s in c.succ.get(n, ()):
            S |= go(s, stack) if s not in stack else {s}
        reach[n] = S
        return S
    # iterative fixpoint (graph has cycles)
    nodes = list(c.insns.keys())
    reach = {n: {n} for n in nodes}
    changed = True
    while changed:
        changed = False
        for n in nodes:
            before = len(reach[n])
            for s in c.succ.get(n, ()):
                if s in reach: reach[n] |= reach[s]
            if len(reach[n]) != before: changed = True
    return reach

def postdom(c, exit_node):
    """post-dominators over the intra-fn graph (single exit assumed/checked)."""
    nodes = sorted(c.insns.keys())
    idx = {n:i for i,n in enumerate(nodes)}
    ALL = (1 << len(nodes)) - 1
    pd = {n: ALL for n in nodes}
    pd[exit_node] = 1 << idx[exit_node]
    changed = True
    while changed:
        changed = False
        for n in reversed(nodes):
            if n == exit_node: continue
            sucs = [s for s in c.succ.get(n, ()) if s in pd]
            if not sucs: continue
            v = ALL
            for s in sucs: v &= pd[s]
            v |= (1 << idx[n])
            if v != pd[n]: pd[n] = v; changed = True
    return pd, idx, nodes

def main():
    im = Img()
    c, IN, OUT = analyse(im, ENTRY)
    dom, idx, nodes = dominators(c, ENTRY)
    reach = build_reach(c)
    pd, pidx, pnodes = postdom(c, RET)
    R = c.reach_backward(CALL)

    # terminators other than RET?
    terms = [n for n in nodes if not c.succ.get(n)]
    print(f"terminator nodes (no successors): {[hex(t) for t in terms]}")
    print(f"single-exit assumption for post-dominance: {'OK' if terms==[RET] else 'VIOLATED'}\n")

    stores = []
    for rva in sorted(c.insns):
        i = c.insns[rva]; o = is_store(i)
        if o is None: continue
        st = IN.get(rva)
        if st is None: continue
        t = mem_this_off(i, st, o)
        if t is None: continue
        stores.append((rva, t, o.size, i))

    def forced(S):
        ds = dom[S]; out = []
        for n in nodes:
            if not ((ds >> idx[n]) & 1): continue
            ins = c.insns[n]
            if ins.mnemonic not in COND: continue
            tgt = ins.operands[0].imm if ins.operands[0].type == X.X86_OP_IMM else None
            ft  = n + ins.size
            treach = tgt is not None and S in reach.get(tgt, ())
            freach = S in reach.get(ft, ())
            if treach and not freach:  out.append((n, ins, 'TAKEN'))
            elif freach and not treach: out.append((n, ins, 'NOT-taken'))
        return out

    print(f"{'rva':>12} {'off':>7} {'w':>3} {'phase':>5} {'domCALL':>7} {'pdRET':>6} {'#forced':>7}  insn")
    for rva, off, w, i in stores:
        phase = 'PRE' if rva in R else ('POST' if RET in reach.get(rva,()) and rva > CALL else '?')
        dc = 'DOM' if (dom[CALL] >> idx[rva]) & 1 else '-'
        pr = 'PD' if (pd[ENTRY] >> pidx[rva]) & 1 else '-'
        f = forced(rva)
        print(f"{rva:#012x} {off:#7x} {w:3d} {phase:>5} {dc:>7} {pr:>6} {len(f):7d}  {i.mnemonic} {i.op_str}")

    print("\n=== FORCED path conditions per store (corrected test) ===")
    for rva, off, w, i in stores:
        f = forced(rva)
        print(f"\n{rva:#010x} off={off:#x} : {i.mnemonic} {i.op_str}")
        for n, ins, dirn in f:
            print(f"    {n:#010x} {ins.mnemonic} {ins.op_str}   must be {dirn}")

    # what post-dominates the CALL's fallthrough (i.e. runs on every path from
    # 'StartNewPhysics returned' to 'ret')
    print("\n=== stores that POST-DOMINATE the call return 0x035EB140 ===")
    pdset = pd[0x035EB140]
    for rva, off, w, i in stores:
        if (pdset >> pidx[rva]) & 1:
            print(f"   {rva:#010x} off={off:#x}  {i.mnemonic} {i.op_str}")

if __name__ == '__main__':
    main()
