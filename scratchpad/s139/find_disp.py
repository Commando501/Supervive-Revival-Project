import sys,struct
from capstone import *
from capstone.x86 import *
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
TEXT_VA=4096; TEXT_SZ=124030976
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
disp=int(sys.argv[1],16)
lo=int(sys.argv[2],16) if len(sys.argv)>2 else TEXT_VA
hi=int(sys.argv[3],16) if len(sys.argv)>3 else TEXT_VA+TEXT_SZ
pat=struct.pack('<i',disp)
i=lo
while True:
    j=d.find(pat,i,hi)
    if j<0: break
    i=j+1
    for back in range(3,12):
        s=j-back
        if s<lo-16: continue
        got=None
        for ins in md.disasm(d[s:s+16],s):
            got=ins; break
        if got and got.address==s and got.address<=j<got.address+got.size:
            hit=False
            for op in got.operands:
                if op.type==X86_OP_MEM and op.mem.disp==disp: hit=True
            if hit:
                print("0x%08x  %s %s"%(s,got.mnemonic,got.op_str)); break
