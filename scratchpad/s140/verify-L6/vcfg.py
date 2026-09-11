import struct
from capstone import *
from capstone.x86 import *
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read(); IB=0x7FF608F40000
TEXT_LO,TEXT_HI=0x1000,0x1000+0x07649000
_md=Cs(CS_ARCH_X86,CS_MODE_64); _md.detail=True
UNCOND={X86_INS_JMP}
COND={X86_INS_JA,X86_INS_JAE,X86_INS_JB,X86_INS_JBE,X86_INS_JCXZ,X86_INS_JECXZ,X86_INS_JRCXZ,
X86_INS_JE,X86_INS_JG,X86_INS_JGE,X86_INS_JL,X86_INS_JLE,X86_INS_JNE,X86_INS_JNO,X86_INS_JNP,
X86_INS_JNS,X86_INS_JO,X86_INS_JP,X86_INS_JS,X86_INS_LOOP,X86_INS_LOOPE,X86_INS_LOOPNE}
class CFG:
    def __init__(self,entry,limit=40000):
        self.entry=entry; self.insns={}; self.succ={}; self.pred={}
        self.calls=[]; self.indirect=[]; self.fail=[]
        wl=[entry]; seen=set()
        while wl:
            a=wl.pop()
            if a in seen: continue
            seen.add(a)
            if not (TEXT_LO<=a<TEXT_HI): continue
            g=list(_md.disasm(D[a:a+16],a))
            if not g:
                self.fail.append(a); continue
            i=g[0]; self.insns[a]=i; self.succ.setdefault(a,set())
            gid=i.group
            if i.id in UNCOND or i.id in COND:
                op=i.operands[0]
                if op.type==X86_OP_IMM:
                    t=op.imm; self.succ[a].add(t); wl.append(t)
                else:
                    self.indirect.append(a)
                if i.id in COND:
                    self.succ[a].add(i.address+i.size); wl.append(i.address+i.size)
            elif i.id==X86_INS_RET or i.id==X86_INS_IRET:
                pass
            elif i.id==X86_INS_INT3 or i.id==X86_INS_UD2:
                pass
            else:
                if i.id==X86_INS_CALL:
                    self.calls.append(a)
                n=i.address+i.size; self.succ[a].add(n); wl.append(n)
            if len(self.insns)>limit: raise RuntimeError("limit")
        for a,s in self.succ.items():
            for t in s: self.pred.setdefault(t,set()).add(a)
        for a in self.insns: self.pred.setdefault(a,set())
    def fwd(self,start):
        r=set(); wl=[start]
        while wl:
            a=wl.pop()
            for t in self.succ.get(a,()):
                if t not in r: r.add(t); wl.append(t)
        return r
    def back(self,target):
        """instructions that can reach target"""
        r={target}; wl=[target]
        while wl:
            a=wl.pop()
            for p in self.pred.get(a,()):
                if p not in r: r.add(p); wl.append(p)
        return r
    def rets(self):
        return [a for a,i in self.insns.items() if i.id==X86_INS_RET]
    def show(self,lo,hi):
        for a in sorted(self.insns):
            if lo<=a<hi:
                i=self.insns[a]
                print(f"  {a:#010x}  {i.bytes.hex(' '):<26} {i.mnemonic} {i.op_str}")
