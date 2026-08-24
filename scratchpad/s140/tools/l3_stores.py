"""L3: enumerate every store to a `this`-relative CMC field in engine
UCharacterMovementComponent::PerformMovement, and rank them as live receipts.

Outputs:
  * every write instruction whose memory operand base register is proven to
    hold `this` (must-analysis, see thistrack.py)
  * per store: on-path-to-call? dominates-the-call? value written
"""
import sys, collections
sys.path.insert(0, '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG
from thistrack import analyse, mem_this_off, preg

ENTRY = 0x035E9EC0
CALL  = 0x035EB13A

# mnemonics that WRITE their first memory operand
W1 = {'mov','movzx','movsx','movsxd','movups','movaps','movsd','movss','movdqu','movdqa',
      'add','sub','and','or','xor','inc','dec','not','neg','shl','shr','sar','rol','ror',
      'adc','sbb','bts','btr','btc','cmpxchg','xchg','xadd','setne','sete','setb','seta',
      'setbe','setae','setl','setg','setle','setge','sets','setns','setp','setnp','seto','setno',
      'movnti','movbe','stosb','stosd','stosq','lock'}
# read-only-memory ops we must NOT count
RO = {'cmp','test','ucomiss','ucomisd','comiss','comisd','push','lea','call','jmp','bt',
      'mulss','mulsd','divss','divsd','addss','addsd','subss','subsd','minss','maxss','minsd','maxsd',
      'sqrtss','sqrtsd','andps','andpd','orps','xorps','andnps','unpcklps','unpckhpd','shufps',
      'cvtsi2ss','cvtsi2sd','cvtss2sd','cvtsd2ss','cvttss2si','cvttsd2si','pxor','por','pand',
      'imul','idiv','mul','div','prefetch','prefetchnta','nop'}

def dominators(c, entry):
    nodes = list(c.insns.keys())
    idx = {n:i for i,n in enumerate(nodes)}
    ALL = (1 << len(nodes)) - 1
    dom = {n: ALL for n in nodes}
    dom[entry] = 1 << idx[entry]
    changed = True
    order = sorted(nodes)
    while changed:
        changed = False
        for n in order:
            if n == entry: continue
            preds = [p for p in c.pred.get(n, ()) if p in dom]
            if not preds: continue
            newv = ALL
            for p in preds: newv &= dom[p]
            newv |= (1 << idx[n])
            if newv != dom[n]:
                dom[n] = newv; changed = True
    return dom, idx, nodes

def main():
    im = Img()
    c, IN, OUT = analyse(im, ENTRY)
    R = c.reach_backward(CALL)          # can reach the call
    dom, idx, nodes = dominators(c, ENTRY)
    dcall = dom[CALL]

    rows = []
    for rva in sorted(c.insns):
        i = c.insns[rva]
        m = i.mnemonic
        if m in RO: continue
        ops = i.operands
        if not ops: continue
        dst = ops[0]
        if dst.type != X.X86_OP_MEM: continue
        if m not in W1 and not m.startswith('set') and not m.startswith('cmov'):
            # unknown mnemonic with a memory dst -- report separately, do not drop
            rows.append((rva, None, None, 'UNKNOWN-MNEMONIC'))
            continue
        st = IN.get(rva)
        if st is None: continue
        off = mem_this_off(i, st, dst)
        if off is None: continue
        rows.append((rva, off, dst.size, None))

    print(f"=== engine PerformMovement {ENTRY:#x}: {len(c.insns)} insns, "
          f"{len(c.calls)} calls, {len(c.indirect_jumps)} indirect jmps, "
          f"{len(c.decode_failures)} decode failures ===")
    print(f"|reach_backward(call {CALL:#x})| = {len(R)}")
    print(f"dominators of call = {bin(dcall).count('1')} instructions\n")
    print(f"{'rva':>12} {'off':>8} {'w':>2}  {'reach':>5} {'dom':>3}  insn")
    unk = []
    for rva, off, w, tag in rows:
        if tag:
            unk.append(rva); continue
        inR  = 'YES' if rva in R else 'no'
        inD  = 'DOM' if (dcall >> idx[rva]) & 1 else '-'
        print(f"{rva:#012x} {off:#8x} {w:2d}  {inR:>5} {inD:>3}  {c.txt(rva)[13:]}")
    if unk:
        print("\nUNKNOWN-MNEMONIC memory-dst instructions (manually adjudicate):")
        for r in unk: print("  ", c.txt(r))

    # also: ALL memory-dst writes whose base was NOT proven this -- so the
    # reader can see the floor
    other = 0
    for rva in sorted(c.insns):
        i = c.insns[rva]
        if i.mnemonic in RO or not i.operands: continue
        dst = i.operands[0]
        if dst.type != X.X86_OP_MEM: continue
        st = IN.get(rva)
        if st is None: continue
        if mem_this_off(i, st, dst) is None:
            other += 1
    print(f"\nmemory-dst writes with base NOT proven this: {other} "
          f"(these are stack/other-object; the this-set above is a MUST set)")

if __name__ == '__main__':
    main()
