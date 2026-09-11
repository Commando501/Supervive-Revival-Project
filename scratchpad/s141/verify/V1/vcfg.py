"""Independent recursive-descent CFG. Written from scratch; classifies MEM writes
from operands[0].type==MEM (NEVER regs_access - S140T2 recorded capstone defect)."""
import collections, capstone
from capstone import x86
from vimg import VImg
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg',
      'jcxz','jecxz','jrcxz','loop','loope','loopne'}
TERM={'ret','retf','iret','iretd','iretq','hlt','ud2','int3'}
class G:
    def __init__(self,im,entry,cap=200000):
        self.im=im; self.entry=entry
        self.I={}; self.succ=collections.defaultdict(set); self.pred=collections.defaultdict(set)
        self.calls={}; self.ijmp=[]; self.fail=[]
        w=[entry]; seen=set()
        while w:
            a=w.pop()
            if a in seen: continue
            seen.add(a)
            assert len(seen)<cap
            try: b=im.read(a,16)
            except ValueError: self.fail.append(a); continue
            it=CS.disasm(b,a)
            try: i=next(it)
            except StopIteration: self.fail.append(a); continue
            self.I[a]=i
            m=i.mnemonic; nx=a+i.size
            def edge(t):
                self.succ[a].add(t); self.pred[t].add(a); w.append(t)
            if m in TERM: continue
            if m=='jmp':
                o=i.operands[0]
                if o.type==x86.X86_OP_IMM: edge(o.imm)
                else: self.ijmp.append(a)
                continue
            if m in COND:
                o=i.operands[0]
                if o.type==x86.X86_OP_IMM: edge(o.imm)
                else: self.ijmp.append(a)
                edge(nx); continue
            if m=='call':
                o=i.operands[0]
                self.calls[a]= o.imm if o.type==x86.X86_OP_IMM else None
                edge(nx); continue
            edge(nx)
    def back(self,t):
        R=set(); st=[t]
        while st:
            n=st.pop()
            if n in R: continue
            R.add(n)
            for p in self.pred.get(n,()): 
                if p not in R: st.append(p)
        return R
    def fwd(self,s):
        R=set(); st=[s]
        while st:
            n=st.pop()
            if n in R: continue
            R.add(n)
            for q in self.succ.get(n,()):
                if q not in R: st.append(q)
        return R
    def doms(self):
        """iterative dominators over instruction graph"""
        nodes=sorted(self.I)
        # only nodes reachable forward from entry
        R=self.fwd(self.entry)
        nodes=[n for n in nodes if n in R]
        D={n:set(nodes) for n in nodes}; D[self.entry]={self.entry}
        ch=True
        while ch:
            ch=False
            for n in nodes:
                if n==self.entry: continue
                ps=[p for p in self.pred.get(n,()) if p in R]
                if not ps: new={n}
                else:
                    new=set(D[ps[0]])
                    for p in ps[1:]: new&=D[p]
                    new.add(n)
                if new!=D[n]: D[n]=new; ch=True
        return D
    def txt(self,a):
        i=self.I.get(a)
        return f"{a:#010x}  {i.bytes.hex():20s} {i.mnemonic} {i.op_str}" if i else f"{a:#010x} ??"
