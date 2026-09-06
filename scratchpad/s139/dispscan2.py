import sys, struct
sys.path.insert(0,'scratchpad/s139')
from img import DATA
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
TEXT_LO,TEXT_HI=0x1000,0x764A000
def scan(disp, window=16, mnem=None):
    pat=struct.pack('<i',disp); hits={}; i=TEXT_LO
    while True:
        i=DATA.find(pat,i,TEXT_HI)
        if i<0: break
        for back in range(1,window):
            a=i-back
            if a<TEXT_LO: continue
            g=list(md.disasm(DATA[a:a+16],a,1))
            if not g: continue
            ins=g[0]
            if ins.address+ins.size < i+4: continue
            if mnem and ins.mnemonic not in mnem: continue
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.disp==disp and op.mem.base not in (X86_REG_RIP,X86_REG_RSP,X86_REG_RBP,0) and op.mem.index==0:
                    hits[a]=ins
        i+=1
    return hits
