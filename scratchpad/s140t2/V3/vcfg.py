# Independent recursive-descent CFG. V3 verifier lane. Not derived from any lane script.
import sys, capstone
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140t2/V3")
from vpe import Img

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

TERM = {capstone.x86.X86_INS_RET, capstone.x86.X86_INS_JMP, capstone.x86.X86_INS_INT3,
        capstone.x86.X86_INS_UD2}
CJMP = set()
for n in dir(capstone.x86):
    if n.startswith('X86_INS_J') and n not in ('X86_INS_JMP',):
        CJMP.add(getattr(capstone.x86, n))
CJMP.discard(capstone.x86.X86_INS_JMP)

def cfg(im, entry, limit_lo=None, limit_hi=None, maxins=20000):
    """Recursive descent. Follows conditional both ways; follows unconditional jmp only if
    the target is inside [limit_lo, limit_hi) (so a tail-jmp out of the function terminates)."""
    seen = {}
    work = [entry]
    calls = []
    tails = []
    rets = []
    indirect_jmps = []
    decode_fail = []
    while work:
        a = work.pop()
        while True:
            if a in seen: break
            if limit_lo is not None and not (limit_lo <= a < limit_hi): break
            code = im.rd(a, 16)
            try:
                ins = next(md.disasm(code, a))
            except StopIteration:
                decode_fail.append(a); break
            seen[a] = ins
            if len(seen) > maxins: raise RuntimeError("runaway")
            g = ins.group  # not used
            mid = ins.id
            if mid == capstone.x86.X86_INS_CALL:
                op = ins.operands[0]
                if op.type == capstone.x86.X86_OP_IMM: calls.append((a, op.imm, 'direct'))
                elif op.type == capstone.x86.X86_OP_MEM: calls.append((a, None, 'mem'))
                else: calls.append((a, None, 'reg'))
                a = ins.address + ins.size
                continue
            if mid == capstone.x86.X86_INS_RET:
                rets.append(a); break
            if mid == capstone.x86.X86_INS_JMP:
                op = ins.operands[0]
                if op.type == capstone.x86.X86_OP_IMM:
                    t = op.imm
                    if limit_lo is not None and limit_lo <= t < limit_hi:
                        a = t; continue
                    else:
                        tails.append((a, t)); break
                else:
                    indirect_jmps.append(a); break
            if mid in CJMP:
                op = ins.operands[0]
                if op.type == capstone.x86.X86_OP_IMM:
                    work.append(op.imm)
                else:
                    indirect_jmps.append(a)
                a = ins.address + ins.size
                continue
            if mid in (capstone.x86.X86_INS_INT3, capstone.x86.X86_INS_UD2):
                break
            a = ins.address + ins.size
    return seen, calls, tails, rets, indirect_jmps, decode_fail

def pr(seen, lo=None, hi=None):
    for a in sorted(seen):
        if lo is not None and not (lo<=a<hi): continue
        i = seen[a]
        print("0x%08x  %-26s %-8s %s" % (a, i.bytes.hex(' '), i.mnemonic, i.op_str))
