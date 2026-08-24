"""S140 recursive-descent CFG over merged13. Shared instrument for lanes A1/A2/A3.

DESIGN NOTES (read before trusting output):
 * Recursive descent from an entry RVA. A LINEAR SWEEP IS UNSOUND here (S139
   measured 1074 vs 1461 instructions on engine PerformMovement).
 * Indirect jumps (jmp reg / jmp [mem]) are recorded as UNRESOLVED successors,
   never silently treated as terminators. If any exist, every reachability
   result is a FLOOR and the caller MUST say so.
 * Calls: fallthrough is assumed. Any call whose fallthrough fails to decode,
   or lands on int3/zero padding, is reported as a NORETURN CANDIDATE.
 * Backward reachability is computed on the instruction graph, so the answer is
   independent of basic-block construction bugs.
"""
import sys, collections
import capstone
sys.path.insert(0, __file__.rsplit('/',1)[0] if '/' in __file__ else '.')
from peimg import Img

CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
CS.detail = True

X86 = capstone.x86

COND = {
 'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg',
 'jcxz','jecxz','jrcxz','loop','loope','loopne'
}
TERM = {'ret','retf','iret','iretd','iretq','hlt','ud2','int3'}

class CFG:
    def __init__(self, img, entry, maxinsn=60000):
        self.img = img; self.entry = entry
        self.insns = {}            # rva -> capstone insn
        self.succ = collections.defaultdict(set)   # rva -> set of successor rvas (intra-fn flow)
        self.pred = collections.defaultdict(set)
        self.calls = {}            # rva -> target (direct) or None (indirect)
        self.indirect_jumps = []   # rvas of jmp reg/[mem]
        self.noreturn_candidates = []
        self.decode_failures = []
        self.tail_jumps = {}       # rva -> target outside explored region (recorded, not followed)
        self._build(maxinsn)

    def _decode(self, rva):
        if rva in self.insns: return self.insns[rva]
        try:
            b = self.img.read(rva, 16)
        except ValueError:
            return None
        g = CS.disasm(b, rva)
        try:
            i = next(g)
        except StopIteration:
            return None
        self.insns[rva] = i
        return i

    def _build(self, maxinsn):
        work = [self.entry]
        seen = set()
        while work:
            rva = work.pop()
            if rva in seen: continue
            seen.add(rva)
            if len(seen) > maxinsn:
                raise RuntimeError("insn cap hit -- runaway walk")
            i = self._decode(rva)
            if i is None:
                self.decode_failures.append(rva); continue
            m = i.mnemonic; nxt = rva + i.size
            if m in TERM:
                continue
            if m == 'jmp':
                op = i.operands[0]
                if op.type == X86.X86_OP_IMM:
                    t = op.imm
                    self.succ[rva].add(t); self.pred[t].add(rva); work.append(t)
                else:
                    self.indirect_jumps.append(rva)
                continue
            if m in COND:
                op = i.operands[0]
                if op.type == X86.X86_OP_IMM:
                    t = op.imm
                    self.succ[rva].add(t); self.pred[t].add(rva); work.append(t)
                else:
                    self.indirect_jumps.append(rva)
                self.succ[rva].add(nxt); self.pred[nxt].add(rva); work.append(nxt)
                continue
            if m == 'call':
                op = i.operands[0]
                self.calls[rva] = op.imm if op.type == X86.X86_OP_IMM else None
                # fallthrough sanity: noreturn candidate detection
                nb = None
                try: nb = self.img.read(nxt, 8)
                except ValueError: pass
                if nb is not None and (nb[0] in (0xCC,) or nb[:4] == b'\0\0\0\0'):
                    self.noreturn_candidates.append((rva, self.calls[rva]))
                self.succ[rva].add(nxt); self.pred[nxt].add(rva); work.append(nxt)
                continue
            self.succ[rva].add(nxt); self.pred[nxt].add(rva); work.append(nxt)

    # ---- analyses ----
    def reach_backward(self, target):
        """Set of instruction rvas that can reach `target` along intra-fn flow."""
        R = set()
        st = [target]
        while st:
            n = st.pop()
            if n in R: continue
            R.add(n)
            for p in self.pred.get(n, ()):
                if p not in R: st.append(p)
        return R

    def exits_from(self, target):
        """Every edge (src -> dst) where src CAN reach target and dst CANNOT.
        This is the SOUND exit set -- direction-agnostic, so backward bails
        are included."""
        R = self.reach_backward(target)
        out = []
        for s in sorted(R):
            for d in sorted(self.succ.get(s, ())):
                if d not in R:
                    out.append((s, d))
        # terminators inside R that have no successors at all are also exits
        for s in sorted(R):
            if s != target and not self.succ.get(s) and self.insns[s].mnemonic in TERM:
                out.append((s, None))
        return out, R

    def txt(self, rva):
        i = self.insns.get(rva)
        return f"{rva:#010x}  {i.mnemonic} {i.op_str}" if i else f"{rva:#010x}  <undecoded>"

def selftest():
    im = Img()
    # POSITIVE CONTROL 1: a known tiny fold. 0xF7EB50 = xor eax,eax; ret -> 2 insns, 0 exits.
    c = CFG(im, 0x00F7EB50)
    assert len(c.insns) == 2, f"fold ctrl: {len(c.insns)} insns"
    assert c.insns[0x00F7EB50].mnemonic == 'xor'
    assert c.insns[0x00F7EB52].mnemonic == 'ret'
    # POSITIVE CONTROL 2: HasValidData 0x035E64C0 -- small real fn, must decode & terminate.
    h = CFG(im, 0x035E64C0)
    assert any(c2.mnemonic=='ret' for c2 in h.insns.values()), "HasValidData no ret"
    # POSITIVE CONTROL 3: backward reachability on a straight line must be the whole prefix.
    #   fold ctrl: reach_backward(ret) == {xor, ret}
    R = c.reach_backward(0x00F7EB52)
    assert R == {0x00F7EB50, 0x00F7EB52}, R
    # NEGATIVE CONTROL: a dark page must decode to garbage/zeros -> 'add [rax],al' chains
    d = im.read(0x5A6AC40, 16)
    assert d == b'\0'*16, "dark control not zero"
    print("CFG selftest: PASS (2 fold insns, HasValidData rets, backward-reach exact, dark ctrl zero)")

if __name__ == '__main__':
    selftest()
    if len(sys.argv) > 1:
        im = Img(); entry = int(sys.argv[1], 16)
        c = CFG(im, entry)
        print(f"entry {entry:#x}: {len(c.insns)} insns, {len(c.calls)} calls, "
              f"{len(c.indirect_jumps)} indirect jumps, {len(c.decode_failures)} decode failures, "
              f"{len(c.noreturn_candidates)} noreturn candidates")
