import sys, struct
sys.path.insert(0,'scratchpad/s139')
from img import DATA, sec_of
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
TEXT_LO,TEXT_HI=0x1000,0x764A000

def scan(disp, window=24):
    pat=struct.pack('<i',disp)
    hits={}
    i=TEXT_LO
    while True:
        i=DATA.find(pat,i,TEXT_HI)
        if i<0: break
        # try decoding starting at each of the preceding `window` bytes; accept if an
        # instruction covers this displacement field exactly and has mem disp == disp
        for back in range(1,window):
            a=i-back
            if a<TEXT_LO: continue
            g=list(md.disasm(DATA[a:a+16],a,1))
            if not g: continue
            ins=g[0]
            if ins.address+ins.size < i+4: continue
            ok=False
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.disp==disp and op.mem.base not in (X86_REG_RIP,X86_REG_RSP,X86_REG_RBP,0):
                    ok=True
            if ok:
                hits.setdefault(a,ins)
                break
        i+=1
    return hits

def is_write(ins):
    # writes if first operand is memory (dest)
    ops=ins.operands
    if not ops: return False
    return ops[0].type==X86_OP_MEM

if __name__=="__main__":
    disp=int(sys.argv[1],16)
    h=scan(disp)
    w=[(a,i) for a,i in sorted(h.items()) if is_write(i)]
    r=[(a,i) for a,i in sorted(h.items()) if not is_write(i)]
    print("disp 0x%X : %d total, %d WRITE-shaped, %d read-shaped"%(disp,len(h),len(w),len(r)))
    print("-- WRITES --")
    for a,i in w: print("0x%08X  %-22s %-8s %s"%(a,i.bytes.hex(),i.mnemonic,i.op_str))
    if len(sys.argv)>2 and sys.argv[2]=='all':
        print("-- READS --")
        for a,i in r: print("0x%08X  %-22s %-8s %s"%(a,i.bytes.hex(),i.mnemonic,i.op_str))
