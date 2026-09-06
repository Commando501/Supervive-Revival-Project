import sys, struct
sys.path.insert(0,r'G:/git/Supervive Revival Project/scratchpad/v10refute')
from lib import *
import capstone
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail=True
def dis(rva, n=0x200, stop_ret=False):
    code = rd(rva,n)
    out=[]
    for i in md.disasm(code, rva):
        s = '0x%08X  %-24s %s %s'%(i.address, i.bytes.hex(), i.mnemonic, i.op_str)
        # annotate rip-relative
        tgt=None
        if i.mnemonic in ('lea','mov','call','jmp','cmp','test') and 'rip' in i.op_str:
            for op in i.operands:
                if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                    tgt = i.address+i.size+op.mem.disp
        if i.mnemonic in ('call','jmp') and i.op_str.startswith('0x'):
            tgt = int(i.op_str,16)
        if tgt is not None:
            s += '   ; -> 0x%08X [%s]'%(tgt, sec_of(tgt))
        out.append(s)
        if stop_ret and i.mnemonic=='ret': break
    return '\n'.join(out)
if __name__=='__main__':
    rva=int(sys.argv[1],16); n=int(sys.argv[2],16) if len(sys.argv)>2 else 0x200
    print(dis(rva,n))
