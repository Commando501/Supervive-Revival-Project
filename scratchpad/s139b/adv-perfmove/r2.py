from advh import *
def show(a,b,label=""):
    print("=== 0x%08X..0x%08X %s"%(a,b,label))
    for i in md.disasm(DATA[a:b],a):
        extra=""
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                extra="  -> 0x%08X"%t
                if 0x0764A000<=t<0x099C7000:
                    extra+="  dword=0x%08X"%struct.unpack_from('<I',DATA,t)[0]
        print("  0x%08X %-16s %-40s%s"%(i.address,i.bytes.hex(),i.mnemonic+" "+i.op_str,extra))
show(0x055C2430,0x055C24A0,"Loki StartNewPhysics (slot228)")
print()
show(0x03600990,0x03600A10,"engine StartNewPhysics")
import struct as S
print()
v=S.unpack('<f',S.pack('<I',0x358637BD))[0]; print("0x358637BD as float =",v)
