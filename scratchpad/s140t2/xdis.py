import sys,struct; sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s140t2')
from pe import PE
import capstone
from capstone import x86
p=PE()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def d(rva,n=0x80,show=True):
    out=[]
    for i in md.disasm(p.rd(rva,n),rva):
        rip=''
        for op in i.operands:
            if op.type==x86.X86_OP_MEM and op.mem.base==x86.X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                rip=' ; -> %#x'%t
        line='%#010x %-22s %s %s%s'%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,rip)
        out.append(line)
        if show: print(line)
    return out
def cfg(entry, limit=200000):
    """recursive-descent over one function; returns {addr: insn}"""
    seen={}; stack=[entry]
    while stack:
        a=stack.pop()
        while True:
            if a in seen: break
            try: code=p.rd(a,16)
            except Exception: break
            ins=list(md.disasm(code,a))
            if not ins: break
            i=ins[0]; seen[a]=i
            g=i.group
            m=i.mnemonic
            if m=='ret' or m.startswith('ret'): break
            if m=='jmp':
                op=i.operands[0]
                if op.type==x86.X86_OP_IMM:
                    t=op.imm
                    if abs(t-entry)<limit: a=t; continue
                break
            if m[0]=='j':
                op=i.operands[0]
                if op.type==x86.X86_OP_IMM and abs(op.imm-entry)<limit: stack.append(op.imm)
            if m=='int3': break
            a=i.address+i.size
    return seen
