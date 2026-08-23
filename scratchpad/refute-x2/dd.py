import sys; sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
p=PE('dumps/merged13.dump.exe'); d=p.data
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
start=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 40
for ins in md.disasm(bytes(d[start:start+n*8]),start):
    print('%08X  %-22s %s %s'%(ins.address,ins.bytes.hex(),ins.mnemonic,ins.op_str))
    n-=1
    if n<=0: break
