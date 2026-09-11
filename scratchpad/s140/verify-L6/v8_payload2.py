import sys,struct
sys.path.insert(0,r'G:\git\Supervive Revival Project\scratchpad\s140\verify-L6')
from vcfg import D,TEXT_LO,TEXT_HI
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
BAD={X86_REG_RSP,X86_REG_RBP,X86_REG_ESP,X86_REG_EBP,X86_REG_RIP}
def allstarts(disp):
    pat=struct.pack('<i',disp); res=[]
    s=TEXT_LO
    while True:
        i=D.find(pat,s)
        if i<0 or i>=TEXT_HI: break
        for back in range(1,16):
            st=i-back
            g=list(md.disasm(D[st:st+16],st))
            if not g: continue
            ins=g[0]
            if ins.address+ins.size<=i+3: continue
            for oi,op in enumerate(ins.operands):
                if op.type==X86_OP_MEM and op.mem.disp==disp and op.mem.base not in BAD:
                    write = (oi==0 and ins.mnemonic not in ('cmp','test','lea','push') )
                    res.append((st,ins.mnemonic,ins.op_str,write,ins.bytes.hex(' ')))
        s=i+1
    return res
for disp in (0x16B0,0x16C0):
    r=[x for x in allstarts(disp) if x[3]]
    print(f"=== disp {disp:#x} : candidate WRITES with non-stack base ({len(r)}) ===")
    for st,m,o,w,b in sorted(set(r)):
        print(f"  {st:#010x} {m} {o:<44} [{b}]")
