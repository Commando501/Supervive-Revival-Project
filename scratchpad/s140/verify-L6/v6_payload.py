import struct
from capstone import *
from capstone.x86 import *
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
D=open(P,'rb').read()
LO,HI=0x1000,0x1000+0x07649000
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def scan(disp):
    pat=struct.pack('<i',disp); cands=[]
    s=LO
    while True:
        i=D.find(pat,s)
        if i<0 or i>=HI: break
        cands.append(i); s=i+1
    out=[]
    for cpos in cands:
        best=None
        for back in range(1,16):
            st=cpos-back
            if st<LO: continue
            g=list(md.disasm(D[st:st+16],st))
            if not g: continue
            ins=g[0]
            if ins.address+ins.size<=cpos+3: continue
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.disp==disp:
                    if best is None: best=(st,ins)
            if best: break
        if best: out.append(best)
    return cands,out
for disp in (0x16B0,0x16C0):
    c,o=scan(disp)
    print(f"=== disp {disp:#x}: {len(c)} byte candidates, {len(o)} decoded MEM refs ===")
    for st,ins in o:
        w = 'W' if ins.operands[0].type==X86_OP_MEM else 'r'
        print(f"  [{w}] {st:#010x} {ins.mnemonic} {ins.op_str}")
