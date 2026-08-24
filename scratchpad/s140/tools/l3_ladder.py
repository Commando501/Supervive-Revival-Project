"""L3 final: the ladder. Union store detector (capstone access-flag OR
memory-dst-position-0 for known store mnemonics), path conditions from
dominators, and context dumps."""
import sys, collections
sys.path.insert(0, '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG
from thistrack import analyse, mem_this_off, preg
from l3_stores import dominators

ENTRY = 0x035E9EC0
CALL  = 0x035EB13A
AC_W  = capstone.CS_AC_WRITE
# capstone 5.0.7 DEFECT: `movups mem, xmm` reports access=READ on the memory
# destination. `movaps`/`movsd`/`movss`/`mov` are correct. Audited over this
# function: movups n=29 (all wrong), movaps n=18 (right), movsd n=30 (right),
# mov n=50 (right), movss n=1 (right); call/cmp/test correctly READ.
FORCE_STORE = {'movups','movdqu','movnps','movntps','movntdq'}
COND = {'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}

def is_store(i):
    if not i.operands: return None
    o = i.operands[0]
    if o.type != X.X86_OP_MEM: return None
    if (o.access & AC_W) or i.mnemonic in FORCE_STORE:
        return o
    return None

def main():
    im = Img()
    c, IN, OUT = analyse(im, ENTRY)
    R  = c.reach_backward(CALL)
    dom, idx, nodes = dominators(c, ENTRY)
    dcall = dom[CALL]
    def fwd(s0):
        S=set(); st=[s0]
        while st:
            n=st.pop()
            if n in S: continue
            S.add(n)
            for s in c.succ.get(n,()):
                if s not in S: st.append(s)
        return S
    POST = fwd(0x035EB140); BAIL = fwd(0x035EB7CF)
    d = {ENTRY:0}; q=collections.deque([ENTRY])
    while q:
        n=q.popleft()
        for s in c.succ.get(n,()):
            if s not in d: d[s]=d[n]+1; q.append(s)

    stores = []
    for rva in sorted(c.insns):
        i = c.insns[rva]; o = is_store(i)
        if o is None: continue
        st = IN.get(rva)
        if st is None: continue
        t = mem_this_off(i, st, o)
        if t is None: continue
        stores.append((rva, t, o.size, i))

    print(f"== ladder for engine PerformMovement {ENTRY:#x} ==")
    print(f"insns={len(c.insns)} calls={len(c.calls)} indirect_jmps={len(c.indirect_jumps)} "
          f"decode_fail={len(c.decode_failures)}")
    print(f"|R(pre-call)|={len(R)} |dom(call)|={bin(dcall).count('1')} |POST|={len(POST)} |BAIL|={len(BAIL)}")
    print(f"this-based stores found: {len(stores)}\n")

    for rva, off, w, i in stores:
        phase = 'PRE ' if rva in R else ('POST' if rva in POST else ('BAIL' if rva in BAIL else '??'))
        isdom = (dcall >> idx[rva]) & 1
        ds = dom[rva]
        conds = []
        for n in nodes:
            if not ((ds >> idx[n]) & 1): continue
            ins = c.insns[n]
            if ins.mnemonic in COND:
                tgt = ins.operands[0].imm if ins.operands[0].type == X.X86_OP_IMM else None
                ft  = n + ins.size
                tin = tgt is not None and ((ds >> idx[tgt]) & 1)
                fin = ((ds >> idx.get(ft, 0)) & 1) if ft in idx else 0
                if tin and not fin:   conds.append(f"{n:#x} {ins.mnemonic} TAKEN")
                elif fin and not tin: conds.append(f"{n:#x} {ins.mnemonic} NOTtaken")
        print(f"[{phase}] {rva:#010x} off={off:#06x} w={w:2d} depth={d.get(rva,-1):4d} "
              f"{'DOMINATES-CALL' if isdom else 'conditional'}")
        print(f"        {i.mnemonic} {i.op_str}")
        if conds:
            print(f"        path condition ({len(conds)}): " + " ; ".join(conds[-6:]))
        print()

if __name__ == '__main__':
    main()
