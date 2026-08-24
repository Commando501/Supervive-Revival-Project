# INDEPENDENT recursive-descent CFG. Written from scratch (does not import cfg.py).
import capstone
from vimg import VImg, IMAGEBASE

CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
CS.detail = True

UNCOND_JMP = {'jmp'}
COND = set("ja jae jb jbe jc jcxz je jecxz jg jge jl jle jne jno jnp jns jo jp jrcxz js".split())
RET  = {'ret','retf','iret','iretd','iretq'}

class VCFG:
    def __init__(self, img, entry, limit=200000):
        self.img=img; self.entry=entry
        self.insns={}          # rva -> capstone insn
        self.succ={}           # rva -> list of rva
        self.pred={}
        self.calls=[]          # (rva, target or None)
        self.indirect_jumps=[]
        self.decode_failures=[]
        self.rets=[]
        work=[entry]; seen=set()
        while work:
            a=work.pop()
            if a in seen: continue
            seen.add(a)
            code = img.read(a, 16)
            if not code or all(b==0 for b in code):
                self.decode_failures.append(a); continue
            try:
                ins = next(CS.disasm(code, a))
            except StopIteration:
                self.decode_failures.append(a); continue
            self.insns[a]=ins
            m=ins.mnemonic; s=[]
            nxt = a+ins.size
            if m in RET:
                self.rets.append(a)
            elif m in UNCOND_JMP:
                op=ins.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    s=[op.imm]
                else:
                    self.indirect_jumps.append(a)
            elif m in COND:
                op=ins.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    s=[op.imm, nxt]
                else:
                    self.indirect_jumps.append(a); s=[nxt]
            elif m=='call':
                op=ins.operands[0]
                t = op.imm if op.type==capstone.x86.X86_OP_IMM else None
                self.calls.append((a,t))
                s=[nxt]
            elif m in ('int3','ud2','hlt'):
                s=[]
            else:
                s=[nxt]
            self.succ[a]=s
            for t in s:
                self.pred.setdefault(t,[]).append(a)
                if t not in seen: work.append(t)
            if len(seen)>limit: raise RuntimeError("limit")
        for a in self.insns: self.pred.setdefault(a,[])
    def nodes(self): return set(self.insns)
    def reach_forward(self, src):
        seen=set(); w=[src]
        while w:
            a=w.pop()
            if a in seen: continue
            seen.add(a)
            for t in self.succ.get(a,[]):
                if t not in seen: w.append(t)
        return seen
    def reach_backward(self, tgt):
        seen=set(); w=[tgt]
        while w:
            a=w.pop()
            if a in seen: continue
            seen.add(a)
            for p in self.pred.get(a,[]):
                if p not in seen: w.append(p)
        return seen
    def dominators(self):
        N=sorted(self.insns)
        allset=set(N)
        dom={n:(set([n]) if n==self.entry else set(allset)) for n in N}
        changed=True
        while changed:
            changed=False
            for n in N:
                if n==self.entry: continue
                ps=[p for p in self.pred.get(n,[]) if p in dom]
                if not ps:
                    new={n}
                else:
                    new=set(dom[ps[0]])
                    for p in ps[1:]: new &= dom[p]
                    new.add(n)
                if new!=dom[n]:
                    dom[n]=new; changed=True
        return dom
    def postdominators(self):
        # exits = ret nodes + nodes with no successors
        N=sorted(self.insns)
        allset=set(N)
        exits=set(self.rets)|{n for n in N if not self.succ.get(n)}
        pdom={n:(set([n]) if n in exits else set(allset)) for n in N}
        changed=True
        while changed:
            changed=False
            for n in reversed(N):
                if n in exits: continue
                ss=[s for s in self.succ.get(n,[]) if s in pdom]
                if not ss: new={n}
                else:
                    new=set(pdom[ss[0]])
                    for s in ss[1:]: new &= pdom[s]
                    new.add(n)
                if new!=pdom[n]:
                    pdom[n]=new; changed=True
        return pdom, exits

if __name__=='__main__':
    im=VImg()
    for name,ent in [("engine PerformMovement",0x035E9EC0)]:
        g=VCFG(im,ent)
        print("%s 0x%X: insns=%d calls=%d indirect_jumps=%d decode_failures=%d rets=%d" %
              (name,ent,len(g.insns),len(g.calls),len(g.indirect_jumps),len(g.decode_failures),len(g.rets)))
        print("  ret addrs:", [hex(r) for r in g.rets])
        print("  indirect jmps:", [hex(r) for r in g.indirect_jumps])
        print("  decode failures:", [hex(r) for r in g.decode_failures])
