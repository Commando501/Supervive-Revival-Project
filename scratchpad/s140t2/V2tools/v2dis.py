import sys
sys.path.insert(0,'scratchpad/s140t2/V2tools')
from v2pe import Img
from capstone import *
from capstone.x86 import *
im=Img('dumps/merged13.dump.exe')
md=Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True
def dis(rva, n=40, end=None):
    data=im.rd(rva, (end-rva) if end else n*15)
    out=[]
    for ins in md.disasm(data, rva):
        out.append(ins)
        if end and ins.address>=end: break
        if not end and len(out)>=n: break
    return out
def show(rva, n=40, end=None, mark=()):
    for ins in dis(rva,n,end):
        m='  <<<' if ins.address in mark else ''
        print(f"{ins.address:08X}  {ins.bytes.hex():<24} {ins.mnemonic:<10} {ins.op_str}{m}")
def wr_ops(ins):
    """classify memory WRITE from operands[0].type == MEM (NOT regs_access)"""
    ops=ins.operands
    if not ops: return None
    if ops[0].type==X86_OP_MEM:
        m=ops[0].mem
        return (ins.reg_name(m.base) if m.base else None, ins.reg_name(m.index) if m.index else None, m.disp)
    return None
