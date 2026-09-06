import sys,struct
from capstone import *
from capstone.x86 import *
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
TEXT_VA=4096; TEXT_SZ=124030976
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
disp=int(sys.argv[1],16)
want=sys.argv[2] if len(sys.argv)>2 else 'call'
pat=struct.pack('<i',disp)
i=TEXT_VA; end=TEXT_VA+TEXT_SZ; out=[]
while True:
    j=d.find(pat,i,end)
    if j<0: break
    i=j+1
    for back in range(2,10):
        s=j-back
        if s<TEXT_VA: continue
        got=None
        for ins in md.disasm(d[s:s+16],s):
            got=ins; break
        if got and got.address==s and s<=j<s+got.size:
            if got.mnemonic==want:
                for op in got.operands:
                    if op.type==X86_OP_MEM and op.mem.disp==disp:
                        out.append((s,got.mnemonic,got.op_str))
            break
print(len(out))
for o in out: print("0x%08x  %s %s"%o)
