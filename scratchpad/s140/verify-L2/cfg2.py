import sys; sys.path.insert(0,'.')
from v import *
from capstone.x86 import *

UNCOND = {'jmp'}
COND = set(['ja','jae','jb','jbe','jc','je','jg','jge','jl','jle','jna','jnae','jnb','jnbe','jnc',
            'jne','jng','jnge','jnl','jnle','jno','jnp','jns','jnz','jo','jp','jpe','jpo','js','jz',
            'jrcxz','jecxz','loop','loope','loopne'])
TERM = {'ret','retf','iret','iretd','iretq','ud2','int3'}

class CFG:
    def __init__(self, img, entry):
        self.img=img; self.entry=entry
        self.insns={}   # rva -> insn
        self.succ={}    # rva -> list
        self.pred={}
        self.calls=[]
        self.indirect_jumps=[]
        self.decode_failures=[]
        self.noreturn_candidates=[]
        work=[entry]; seen=set()
        while work:
            a=work.pop()
            if a in seen: continue
            seen.add(a)
            try:
                ins=list(md.disasm(img.read(a,32), a))
            except Exception:
                self.decode_failures.append(a); continue
            if not ins:
                self.decode_failures.append(a); continue
            i=ins[0]
            self.insns[a]=i
            s=[]
            m=i.mnemonic
            if m in TERM:
                pass
            elif m in UNCOND:
                op=i.operands[0]
                if op.type==X86_OP_IMM: s=[op.imm]
                else:
                    self.indirect_jumps.append(a)
            elif m in COND:
                op=i.operands[0]
                if op.type==X86_OP_IMM: s=[op.imm, a+i.size]
                else:
                    self.indirect_jumps.append(a); s=[a+i.size]
            elif m=='call':
                op=i.operands[0]
                if op.type==X86_OP_IMM: self.calls.append((a,op.imm))
                else: self.calls.append((a,None))
                s=[a+i.size]
            else:
                s=[a+i.size]
            self.succ[a]=s
            for t in s: work.append(t)
        for a,ss in self.succ.items():
            for t in ss:
                self.pred.setdefault(t,[]).append(a)
        for a in self.insns:
            self.pred.setdefault(a,[])

    def reach_backward(self, target):
        """set of nodes from which target is reachable (excluding via target itself as source)"""
        R=set([target]); work=[target]
        while work:
            n=work.pop()
            for p in self.pred.get(n,[]):
                if p not in R:
                    R.add(p); work.append(p)
        return R

    def exits_from(self, target, include_target_as_source=False):
        R=self.reach_backward(target)
        out=[]
        for n in sorted(R):
            if n==target and not include_target_as_source: continue
            for t in self.succ.get(n,[]):
                if t not in R:
                    out.append((n,t))
        return R,out

    def reach_forward(self, start):
        F=set([start]); work=[start]
        while work:
            n=work.pop()
            for t in self.succ.get(n,[]):
                if t not in F:
                    F.add(t); work.append(t)
        return F
