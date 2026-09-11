import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l5img as I
from capstone import *
from capstone.x86 import *
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
def dis(rva, n=60, stop_ret=True):
    code = I.DATA[rva:rva+n*16]
    out=[]
    for ins in md.disasm(code, I.IMAGEBASE+rva):
        r = ins.address - I.IMAGEBASE
        txt = f"{r:#010x}  {ins.bytes.hex():<24} {ins.mnemonic} {ins.op_str}"
        # annotate rip-relative
        if 'rip' in ins.op_str:
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    tgt = ins.address + ins.size + op.mem.disp - I.IMAGEBASE
                    txt += f"   ; [rva {tgt:#x} {I.sec_of(tgt)}]"
        if ins.mnemonic in ('call','jmp') and ins.operands and ins.operands[0].type==X86_OP_IMM:
            t = ins.operands[0].imm - I.IMAGEBASE
            txt += f"   ; -> {t:#x}"
        out.append(txt)
        if len(out)>=n: break
        if stop_ret and ins.mnemonic in ('ret','jmp') and ins.mnemonic=='ret': break
    return "\n".join(out)
if __name__=='__main__':
    rva=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 60
    print(dis(rva,n))
