import struct, sys, collections
from capstone import *
from capstone.x86 import *
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from v import Img, im

md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True

UNCOND = {X86_INS_JMP}
CC = {X86_INS_JA,X86_INS_JAE,X86_INS_JB,X86_INS_JBE,X86_INS_JCXZ,X86_INS_JECXZ,X86_INS_JRCXZ,
      X86_INS_JE,X86_INS_JG,X86_INS_JGE,X86_INS_JL,X86_INS_JLE,X86_INS_JNE,X86_INS_JNO,
      X86_INS_JNP,X86_INS_JNS,X86_INS_JO,X86_INS_JP,X86_INS_JS,X86_INS_LOOP,X86_INS_LOOPE,X86_INS_LOOPNE}
TERM = {X86_INS_RET,X86_INS_RETF,X86_INS_RETFQ,X86_INS_IRET,X86_INS_IRETD,X86_INS_IRETQ,
        X86_INS_UD0,X86_INS_UD1,X86_INS_UD2,X86_INS_INT3,X86_INS_HLT}

class CFG2:
    def __init__(self, img, entry, tail_limit=0x2000):
        self.img=img; self.entry=entry
        self.ins={}          # addr -> (size, mnem, opstr, insn)
        self.succ=collections.defaultdict(list)
        self.pred=collections.defaultdict(list)
        self.calls=[]        # (site, target or None)
        self.indirect_jumps=[]
        self.rets=[]
        self.terms=[]
        self.decode_failures=[]
        self.tail_jmps=[]
        wl=[entry]; seen=set()
        while wl:
            a=wl.pop()
            if a in seen: continue
            seen.add(a)
            data=img.read(a,24)
            g=list(md.disasm(data,a))
            if not g:
                self.decode_failures.append(a); continue
            i=g[0]
            self.ins[a]=(i.size,i.mnemonic,i.op_str,i)
            nxt=a+i.size
            ss=[]
            gid=i.id
            if gid==X86_INS_CALL:
                op=i.operands[0]
                tgt = op.imm if op.type==X86_OP_IMM else None
                self.calls.append((a,tgt))
                ss=[nxt]                       # calls assumed to return
            elif gid in UNCOND:
                op=i.operands[0]
                if op.type==X86_OP_IMM:
                    t=op.imm
                    if abs(t-a)>tail_limit: self.tail_jmps.append((a,t))
                    ss=[t]
                else:
                    self.indirect_jumps.append(a); ss=[]
            elif gid in CC:
                op=i.operands[0]
                if op.type==X86_OP_IMM: ss=[op.imm,nxt]
                else: self.indirect_jumps.append(a); ss=[nxt]
            elif gid in TERM:
                if gid in (X86_INS_RET,X86_INS_RETF,X86_INS_RETFQ): self.rets.append(a)
                self.terms.append(a); ss=[]
            else:
                ss=[nxt]
            self.succ[a]=ss
            for s in ss:
                self.pred[s].append(a)
                if s not in seen: wl.append(s)
    def reach_backward(self, t):
        R={t}; wl=[t]
        while wl:
            n=wl.pop()
            for p in self.pred.get(n,()):
                if p not in R: R.add(p); wl.append(p)
        return R
    def reach_forward(self, starts):
        F=set(starts); wl=list(starts)
        while wl:
            n=wl.pop()
            for s in self.succ.get(n,()):
                if s not in F: F.add(s); wl.append(s)
        return F

if __name__=="__main__":
    ENTRY=0x035E9EC0; CALL=0x035EB13A
    c=CFG2(im, ENTRY)
    direct=[t for (s,t) in c.calls if t is not None]
    indirect=[s for (s,t) in c.calls if t is None]
    print("insns          :", len(c.ins))
    print("calls          :", len(c.calls), " direct sites:", len(direct), " distinct direct:", len(set(direct)), " indirect sites:", len(indirect))
    print("indirect jumps :", len(c.indirect_jumps), c.indirect_jumps)
    print("rets           :", len(c.rets), [hex(x) for x in c.rets])
    print("other terms    :", [(hex(a),c.ins[a][1]) for a in c.terms if a not in c.rets])
    print("decode failures:", c.decode_failures)
    print("tail jmps      :", [(hex(a),hex(t)) for a,t in c.tail_jmps])
    lo=min(c.ins); hi=max(a+c.ins[a][0] for a in c.ins)
    print("addr range     :", hex(lo),"..",hex(hi)," span",hex(hi-lo))
    # gap analysis
    cov=bytearray(hi-lo)
    for a,(sz,_,_,_) in c.ins.items():
        for k in range(sz): cov[a-lo+k]=1
    gaps=[];run=None
    for k,v in enumerate(cov):
        if not v:
            if run is None: run=k
        else:
            if run is not None: gaps.append((lo+run,k-run)); run=None
    if run is not None: gaps.append((lo+run,len(cov)-run))
    print(f"coverage: total {hi-lo} covered {sum(cov)} gaps {len(gaps)} regions / {hi-lo-sum(cov)} bytes")
    for g in gaps[:20]: print("   gap", hex(g[0]), g[1])
