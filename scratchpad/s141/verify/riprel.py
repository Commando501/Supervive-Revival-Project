from v import im
from capstone import *
from capstone.x86 import *
import struct,sys
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def riprel(rva,n=0x140):
    for i in md.disasm(im.read(rva,n),rva):
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                tgt=i.address+i.size+op.mem.disp
                s=im.sec_of(tgt)
                sec=s['name'] if s else '??'
                try: b=im.read(tgt,24).hex()
                except: b='<oob>'
                print("%#09x %-8s %-34s -> %#09x [%s] bytes=%s"%(i.address,i.mnemonic,i.op_str,tgt,sec,b))
if __name__=='__main__':
    riprel(int(sys.argv[1],16), int(sys.argv[2],16) if len(sys.argv)>2 else 0x140)
