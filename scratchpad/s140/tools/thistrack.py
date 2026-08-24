"""L3: must-analysis register tracker for 'which register holds `this`'.

Lattice per 64-bit register / tracked stack slot:
    None                -> UNKNOWN (top of the "not this" world; we only ever
                           claim THIS when we can prove it)
    ('this', d)         -> value == this + d
    ('frame', d)        -> value == RSP_at_function_entry + d   (for rsp/rbp)

Join at CFG merge points is INTERSECTION (must-analysis): a register is THIS on
entry to a block only if it is THIS with the SAME displacement on every
predecessor edge. That makes every THIS claim sound; it can only UNDER-report.

Win64 ABI: volatile = rax rcx rdx r8 r9 r10 r11 (+ xmm0-5). Non-volatile =
rbx rbp rdi rsi rsp r12 r13 r14 r15. A `call` kills every volatile register.
"""
import sys, collections
sys.path.insert(0, __file__.rsplit('\\',1)[0] if '\\' in __file__ else '.')
import capstone
from capstone import x86 as X
from peimg import Img
from cfg import CFG, CS

VOLATILE = {'rax','rcx','rdx','r8','r9','r10','r11'}
REG64 = ['rax','rbx','rcx','rdx','rsi','rdi','rbp','rsp',
         'r8','r9','r10','r11','r12','r13','r14','r15']

# map any capstone reg id to its 64-bit parent name (None if not a GPR)
_P = {}
def _mkparent():
    fam = {
     'rax':['rax','eax','ax','al','ah'], 'rbx':['rbx','ebx','bx','bl','bh'],
     'rcx':['rcx','ecx','cx','cl','ch'], 'rdx':['rdx','edx','dx','dl','dh'],
     'rsi':['rsi','esi','si','sil'], 'rdi':['rdi','edi','di','dil'],
     'rbp':['rbp','ebp','bp','bpl'], 'rsp':['rsp','esp','sp','spl'],
    }
    for i in range(8,16):
        fam[f'r{i}'] = [f'r{i}', f'r{i}d', f'r{i}w', f'r{i}b']
    for p, names in fam.items():
        for n in names:
            _P[n] = p
_mkparent()

def parent(name):
    return _P.get(name)

def preg(insn, rid):
    if rid == 0: return None
    return parent(insn.reg_name(rid))

class State:
    __slots__ = ('regs','stack')
    def __init__(self, regs=None, stack=None):
        self.regs = dict(regs) if regs else {}
        self.stack = dict(stack) if stack else {}
    def copy(self):
        return State(self.regs, self.stack)
    def __eq__(self, o):
        return self.regs == o.regs and self.stack == o.stack
    def meet(self, o):
        r = {k:v for k,v in self.regs.items() if o.regs.get(k) == v}
        s = {k:v for k,v in self.stack.items() if o.stack.get(k) == v}
        return State(r, s)
    def get(self, reg):
        return self.regs.get(reg)
    def kill(self, reg):
        self.regs.pop(reg, None)
    def set(self, reg, val):
        if val is None: self.regs.pop(reg, None)
        else: self.regs[reg] = val

def mem_frame_off(insn, st, op):
    """If op is a stack slot [rsp/rbp + disp] with a known frame value, return
    the FRAME-relative offset; else None."""
    m = op.mem
    if m.index != 0: return None
    b = preg(insn, m.base)
    if b is None: return None
    v = st.get(b)
    if v is None or v[0] != 'frame': return None
    return v[1] + m.disp

def mem_this_off(insn, st, op):
    """If op is [reg + disp] where reg is THIS-derived and there is no index,
    return the this-relative offset; else None."""
    m = op.mem
    if m.index != 0: return None
    b = preg(insn, m.base)
    if b is None: return None
    v = st.get(b)
    if v is None or v[0] != 'this': return None
    return v[1] + m.disp

def transfer(insn, st_in):
    """Return (st_out, note). Conservative: anything not modelled kills its
    written registers."""
    st = st_in.copy()
    m = insn.mnemonic
    ops = insn.operands

    if m == 'push':
        v = st.get('rsp')
        if v and v[0]=='frame': st.set('rsp', ('frame', v[1]-8))
        else: st.kill('rsp')
        return st, None
    if m == 'pop':
        v = st.get('rsp')
        if v and v[0]=='frame': st.set('rsp', ('frame', v[1]+8))
        else: st.kill('rsp')
        if ops and ops[0].type == X.X86_OP_REG:
            st.kill(preg(insn, ops[0].reg))
        return st, None
    if m == 'call':
        for r in VOLATILE: st.kill(r)
        return st, None
    if m == 'ret':
        return st, None

    if m == 'lea' and len(ops) == 2 and ops[0].type == X.X86_OP_REG:
        d = preg(insn, ops[0].reg)
        mm = ops[1].mem
        if mm.index == 0:
            b = preg(insn, mm.base)
            v = st.get(b) if b else None
            if v is not None:
                st.set(d, (v[0], v[1] + mm.disp)); return st, None
        st.kill(d); return st, None

    if m == 'mov' and len(ops) == 2:
        dst, src = ops
        if dst.type == X.X86_OP_REG:
            d = preg(insn, dst.reg)
            if d is None: return st, None
            # 8/16-bit writes are partial: they do NOT establish a pointer, and
            # they also do not fully clobber. Treat as kill (sound).
            if dst.size != 8:
                st.kill(d); return st, None
            if src.type == X.X86_OP_REG:
                s = preg(insn, src.reg)
                st.set(d, st.get(s) if (s and src.size==8) else None); return st, None
            if src.type == X.X86_OP_MEM:
                fo = mem_frame_off(insn, st, src)
                if fo is not None and src.size == 8:
                    st.set(d, st.stack.get(fo)); return st, None
                st.kill(d); return st, None
            st.kill(d); return st, None
        if dst.type == X.X86_OP_MEM and src.type == X.X86_OP_REG and dst.size == 8:
            fo = mem_frame_off(insn, st, dst)
            s = preg(insn, src.reg)
            if fo is not None:
                st.stack[fo] = st.get(s) if s else None
            return st, None
        return st, None

    if m in ('add','sub') and len(ops)==2 and ops[0].type==X.X86_OP_REG and ops[1].type==X.X86_OP_IMM:
        d = preg(insn, ops[0].reg)
        v = st.get(d)
        if v is not None and ops[0].size==8:
            k = ops[1].imm if m=='add' else -ops[1].imm
            st.set(d, (v[0], v[1]+k))
        else:
            st.kill(d)
        return st, None

    # default: kill every written register
    try:
        _, wr = insn.regs_access()
    except Exception:
        wr = []
    for rid in wr:
        p = preg(insn, rid)
        if p: st.kill(p)
    return st, None


def analyse(img, entry):
    c = CFG(img, entry)
    init = State()
    init.set('rcx', ('this', 0))
    init.set('rsp', ('frame', 0))
    IN = {entry: init}
    work = [entry]
    OUT = {}
    it = 0
    while work:
        it += 1
        if it > 400000: raise RuntimeError('no fixpoint')
        n = work.pop()
        si = IN.get(n)
        if si is None: continue
        so, _ = transfer(c.insns[n], si)
        old = OUT.get(n)
        if old is not None and old == so and n in OUT:
            pass
        OUT[n] = so
        for s in c.succ.get(n, ()):
            cur = IN.get(s)
            new = so if cur is None else cur.meet(so)
            if cur is None or not (cur == new):
                IN[s] = new
                work.append(s)
    return c, IN, OUT

if __name__ == '__main__':
    im = Img()
    entry = int(sys.argv[1],16) if len(sys.argv)>1 else 0x035E9EC0
    c, IN, OUT = analyse(im, entry)
    print(f"entry {entry:#x}: {len(c.insns)} insns, IN states for {len(IN)}")
    # CONTROLS
    for a, want in ((0x035E9F82,'rbx'), (0x035EB130,'rbx')):
        st = IN.get(a)
        print(f"CTRL {a:#x}: {c.txt(a)}   rbx={st.get('rbx') if st else 'NO STATE'}")
