import struct
from capstone import *
from capstone.x86 import *
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
TEXT_VA=4096; TEXT_SZ=124030976
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
pat=b'\x18\x04\x00\x00'
hits=[]
i=TEXT_VA
end=TEXT_VA+TEXT_SZ
while True:
    j=d.find(pat,i,end)
    if j<0: break
    i=j+1
    # try to decode an instruction covering j with disp==0x418
    ok=None
    for back in range(3,12):
        s=j-back
        if s<TEXT_VA: continue
        for ins in md.disasm(d[s:s+16],s):
            if ins.address!=s: break
            # check operand disp
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.disp==0x418 and ins.address<=j<ins.address+ins.size:
                    ok=(s,ins)
            break
        if ok: break
    if ok: hits.append((ok[0],ok[1].mnemonic,ok[1].op_str))
print(len(hits))
for h in hits[:400]: print(hex(h[0]),h[1],h[2])
