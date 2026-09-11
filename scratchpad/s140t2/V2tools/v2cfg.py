# recursive-descent CFG, written for this verification lane
import sys; sys.path.insert(0,'scratchpad/s140t2/V2tools')
from v2dis import im, md
from capstone import *
from capstone.x86 import *
UNCOND_END={X86_INS_RET,X86_INS_JMP,X86_INS_INT3,X86_INS_UD2,X86_INS_IRET}
COND={X86_INS_JA,X86_INS_JAE,X86_INS_JB,X86_INS_JBE,X86_INS_JCXZ,X86_INS_JECXZ,X86_INS_JE,
 X86_INS_JG,X86_INS_JGE,X86_INS_JL,X86_INS_JLE,X86_INS_JNE,X86_INS_JNO,X86_INS_JNP,
 X86_INS_JNS,X86_INS_JO,X86_INS_JP,X86_INS_JRCXZ,X86_INS_JS,X86_INS_LOOP,X86_INS_LOOPE,X86_INS_LOOPNE}
def walk(entry, limit=0x20000):
    seen={}; work=[entry]; bad=0; indirect_jmp=0
    lo=entry; hi=entry
    while work:
        a=work.pop()
        while True:
            if a in seen: break
            data=im.rd(a,16)
            g=list(md.disasm(data,a,1))
            if not g:
                bad+=1; break
            ins=g[0]; seen[a]=ins
            lo=min(lo,a); hi=max(hi,a+ins.size)
            if abs(a-entry)>limit: break
            if ins.id in COND:
                op=ins.operands[0]
                if op.type==X86_OP_IMM: work.append(op.imm)
                a=a+ins.size; continue
            if ins.id==X86_INS_JMP:
                op=ins.operands[0]
                if op.type==X86_OP_IMM:
                    a=op.imm; continue
                indirect_jmp+=1; break
            if ins.id in UNCOND_END: break
            a=a+ins.size
    return seen,bad,indirect_jmp,lo,hi
def mem_writes(seen, disps=None, bases_excl=('rsp','rbp','rip')):
    out=[]
    for a in sorted(seen):
        ins=seen[a]
        ops=ins.operands
        if not ops: continue
        if ops[0].type!=X86_OP_MEM: continue
        m=ops[0].mem
        b=ins.reg_name(m.base) if m.base else None
        if b in bases_excl: continue
        if disps is not None and m.disp not in disps: continue
        out.append((a,ins.mnemonic,ins.op_str,b,m.disp))
    return out
def mem_any(seen, disps, bases_excl=('rsp','rip')):
    out=[]
    for a in sorted(seen):
        ins=seen[a]
        for i,op in enumerate(ins.operands):
            if op.type!=X86_OP_MEM: continue
            m=op.mem
            b=ins.reg_name(m.base) if m.base else None
            if b in bases_excl: continue
            if m.disp in disps:
                out.append((a,ins.mnemonic,ins.op_str,b,m.disp,'W' if i==0 else 'R'))
    return out
