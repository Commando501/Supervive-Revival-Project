# V1: independent recursive-descent CFG. Written from scratch for the verification lane.
from capstone import *
from capstone.x86 import *

COND = set(['jo','jno','js','jns','je','jz','jne','jnz','jb','jnae','jc','jnb','jae','jnc',
            'jbe','jna','ja','jnbe','jl','jnge','jge','jnl','jle','jng','jg','jnle','jp',
            'jpe','jnp','jpo','jcxz','jecxz','jrcxz','loop','loope','loopne'])
TERM = set(['ret','retf','iret','iretd','iretq','ud2','hlt'])

class CFG:
    def __init__(self, img, entry, maxbytes=0x20000):
        self.md = Cs(CS_ARCH_X86, CS_MODE_64); self.md.detail = True
        self.img = img; self.entry = entry
        self.ins = {}          # addr -> insn
        self.succ = {}         # addr -> list of (target, kind)
        self.pred = {}
        self.decode_fail = []
        self.calls = []        # (addr, target or None, indirect?)
        self.indirect_jumps = []
        self.rets = []
        self._walk(entry, maxbytes)
        for a, ss in self.succ.items():
            for (t,k) in ss:
                self.pred.setdefault(t, []).append((a,k))
    def _dis1(self, addr):
        b = self.img.read(addr, 16)
        for i in self.md.disasm(b, addr):
            return i
        return None
    def _walk(self, entry, maxbytes):
        lo, hi = entry, entry+maxbytes
        work=[entry]; seen=set()
        while work:
            a = work.pop()
            while True:
                if a in seen: break
                if not (lo <= a < hi): break
                i = self._dis1(a)
                if i is None:
                    self.decode_fail.append(a); break
                seen.add(a); self.ins[a]=i
                nxt = a + i.size
                m = i.mnemonic; s=[]
                if m == 'call':
                    op = i.operands[0]
                    if op.type == X86_OP_IMM:
                        self.calls.append((a, op.imm, False))
                    else:
                        self.calls.append((a, None, True))
                    s.append((nxt,'fall'))
                elif m == 'jmp':
                    op = i.operands[0]
                    if op.type == X86_OP_IMM:
                        s.append((op.imm,'jmp'))
                    else:
                        self.indirect_jumps.append(a)
                elif m in COND:
                    op = i.operands[0]
                    if op.type == X86_OP_IMM:
                        s.append((op.imm,'jcc'))
                    s.append((nxt,'fall'))
                elif m in TERM:
                    if m.startswith('ret'): self.rets.append(a)
                else:
                    s.append((nxt,'fall'))
                self.succ[a]=s
                cont=None
                for (t,k) in s:
                    if k=='fall': cont=t
                    elif lo<=t<hi: work.append(t)
                if cont is None: break
                a=cont
    def span(self):
        if not self.ins: return (0,0,0,0)
        lo=min(self.ins); hi=max(a+self.ins[a].size for a in self.ins)
        covered=sum(self.ins[a].size for a in self.ins)
        return lo,hi,hi-lo,covered
    def reach_fwd(self, start, banned=frozenset()):
        R=set(); w=[start]
        while w:
            a=w.pop()
            if a in R or a in banned: continue
            if a not in self.succ: 
                R.add(a); continue
            R.add(a)
            for (t,k) in self.succ[a]:
                if t in self.ins and t not in R: w.append(t)
        return R
    def reach_bwd(self, target):
        R=set(); w=[target]
        while w:
            a=w.pop()
            if a in R: continue
            R.add(a)
            for (p,k) in self.pred.get(a,[]):
                if p not in R: w.append(p)
        return R
