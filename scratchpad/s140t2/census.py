import sys; sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s140t2')
from xdis import *
from capstone import x86
import struct, json

GPR_OK = set()
for r in range(x86.X86_REG_AH, x86.X86_REG_ENDING): GPR_OK.add(r)
BAD = {x86.X86_REG_RSP, x86.X86_REG_RBP, x86.X86_REG_RIP, x86.X86_REG_INVALID}

def funcbody(entry, maxspan=0x6000):
    """recursive descent, single function"""
    seen={}; stack=[entry]
    while stack:
        a=stack.pop()
        while True:
            if a in seen: break
            if not (entry-0x200 <= a <= entry+maxspan): break
            try: code=p.rd(a,16)
            except Exception: break
            ins=list(md.disasm(code,a))
            if not ins: break
            i=ins[0]; seen[a]=i; m=i.mnemonic
            if m.startswith('ret') or m=='int3' or m=='ud2': break
            if m=='jmp':
                op=i.operands[0]
                if op.type==x86.X86_OP_IMM and entry-0x200<=op.imm<=entry+maxspan: a=op.imm; continue
                break
            if m[0]=='j' and m!='jmp':
                op=i.operands[0]
                if op.type==x86.X86_OP_IMM: stack.append(op.imm)
            a=i.address+i.size
    return seen

def scan_disp(insns, disps):
    hits=[]
    for a,i in sorted(insns.items()):
        for k,op in enumerate(i.operands):
            if op.type==x86.X86_OP_MEM and op.mem.base not in BAD and op.mem.disp in disps and op.mem.index==0:
                iswrite = (k==0 and i.operands[0].type==x86.X86_OP_MEM and len(i.operands)>1)
                hits.append((a,i.mnemonic,i.op_str,op.mem.disp,'W' if iswrite else 'R',i.bytes.hex()))
    return hits
