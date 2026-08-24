"""L3 v2: robust store enumeration using capstone operand ACCESS flags rather
than a mnemonic whitelist (the whitelist is a floor and can silently drop)."""
import sys, collections
sys.path.insert(0, '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG
from thistrack import analyse, mem_this_off, mem_frame_off, preg

ENTRY = 0x035E9EC0
CALL  = 0x035EB13A
AC_W = capstone.CS_AC_WRITE

def mem_write_ops(i):
    out = []
    for o in i.operands:
        if o.type == X.X86_OP_MEM and (o.access & AC_W):
            out.append(o)
    return out

def dominators(c, entry):
    nodes = sorted(c.insns.keys())
    idx = {n:i for i,n in enumerate(nodes)}
    ALL = (1 << len(nodes)) - 1
    dom = {n: ALL for n in nodes}
    dom[entry] = 1 << idx[entry]
    changed = True
    while changed:
        changed = False
        for n in nodes:
            if n == entry: continue
            preds = [p for p in c.pred.get(n, ()) if p in dom]
            if not preds: continue
            v = ALL
            for p in preds: v &= dom[p]
            v |= (1 << idx[n])
            if v != dom[n]: dom[n] = v; changed = True
    return dom, idx, nodes

def shortest_depth(c, entry):
    """BFS instruction-count depth from entry (a rough ladder ordinate)."""
    d = {entry: 0}
    q = collections.deque([entry])
    while q:
        n = q.popleft()
        for s in c.succ.get(n, ()):
            if s not in d:
                d[s] = d[n] + 1; q.append(s)
    return d

def main():
    im = Img()
    c, IN, OUT = analyse(im, ENTRY)
    R = c.reach_backward(CALL)
    dom, idx, nodes = dominators(c, ENTRY)
    dcall = dom[CALL]
    depth = shortest_depth(c, ENTRY)

    this_st, frame_st, other_st = [], [], []
    for rva in sorted(c.insns):
        i = c.insns[rva]
        st = IN.get(rva)
        for o in mem_write_ops(i):
            if st is None:
                other_st.append((rva, 'NOSTATE', o.size)); continue
            t = mem_this_off(i, st, o)
            if t is not None:
                this_st.append((rva, t, o.size)); continue
            f = mem_frame_off(i, st, o)
            if f is not None:
                frame_st.append((rva, f, o.size)); continue
            b = preg(i, o.mem.base) if o.mem.base else None
            other_st.append((rva, b, o.size))

    print(f"engine PerformMovement {ENTRY:#x}  insns={len(c.insns)}  calls={len(c.calls)}  "
          f"indirect_jmp={len(c.indirect_jumps)}  decode_fail={len(c.decode_failures)}")
    print(f"|reach_backward({CALL:#x})|={len(R)}   |dom(call)|={bin(dcall).count('1')}")
    print(f"memory-WRITE operands: this-based={len(this_st)} frame/stack={len(frame_st)} "
          f"other={len(other_st)}\n")

    print(f"{'rva':>12} {'off':>7} {'w':>3} {'depth':>5} {'reach':>5} {'dom':>4}  instruction")
    for rva, off, w in this_st:
        print(f"{rva:#012x} {off:#7x} {w:3d} {depth.get(rva,-1):5d} "
              f"{'YES' if rva in R else 'no':>5} {'DOM' if (dcall>>idx[rva])&1 else '-':>4}  "
              f"{c.insns[rva].mnemonic} {c.insns[rva].op_str}")

    print("\n-- 'other' bases (sanity: must be non-this objects/stack) --")
    cnt = collections.Counter(b for _,b,_ in other_st)
    print("   base-register histogram:", dict(cnt))

if __name__ == '__main__':
    main()
