# L2 independent disassembly driver (does NOT import cfg.py)
import sys
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from capstone import *
from capstone.x86 import *

def md():
    m = Cs(CS_ARCH_X86, CS_MODE_64)
    m.detail = True
    return m

def lin(img, rva, n, mdl=None):
    """LINEAR sweep - UNSOUND for CFG, fine for reading a known contiguous block."""
    m = mdl or md()
    data = img.read(rva, n)
    return list(m.disasm(data, rva))

def fmt(i, img=None):
    s = "%08X  %-26s %-8s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str)
    # annotate rip-relative target
    for op in i.operands:
        if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
            tgt = i.address + i.size + op.mem.disp
            s += "   ; [rip] -> 0x%08X" % tgt
    return s

# ---- SOUND recursive-descent CFG, written independently ----
UNCOND = {X86_INS_JMP}
RET    = {X86_INS_RET, X86_INS_RETF, X86_INS_IRET, X86_INS_UD2}
def is_cond(i):
    return X86_GRP_JUMP in i.groups and i.id != X86_INS_JMP

def cfg(img, entry, limit_lo=None, limit_hi=None, maxn=200000):
    """Recursive descent. Returns dict addr->insn, plus succ edges."""
    m = md()
    insns = {}
    succ = {}
    work = [entry]
    seen = set()
    bad = []
    while work:
        a = work.pop()
        while True:
            if a in insns: break
            if limit_lo is not None and not (limit_lo <= a < limit_hi):
                break
            try:
                data = img.read(a, 16)
            except Exception:
                bad.append(a); break
            g = list(m.disasm(data, a, count=1))
            if not g:
                bad.append(a); break
            i = g[0]
            insns[a] = i
            s = []
            if i.id in RET:
                succ[a] = []
                break
            if i.id == X86_INS_JMP:
                op = i.operands[0]
                if op.type == X86_OP_IMM:
                    t = op.imm
                    s = [t]; work.append(t)
                else:
                    s = []   # indirect jmp -> unknown
                succ[a] = s
                break
            if is_cond(i):
                op = i.operands[0]
                t = op.imm if op.type == X86_OP_IMM else None
                nxt = a + i.size
                s = ([t] if t is not None else []) + [nxt]
                succ[a] = s
                if t is not None: work.append(t)
                a = nxt
                continue
            # normal / call: falls through
            succ[a] = [a + i.size]
            a = a + i.size
    return insns, succ, bad

if __name__ == '__main__':
    img = L2Img('dumps/merged14.dump.exe')
    lo = int(sys.argv[1],16); n = int(sys.argv[2],16)
    for i in lin(img, lo, n):
        print(fmt(i, img))
