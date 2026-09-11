exec(open(r"scratchpad/s140/syn/adj3.py").read().split("for E,name in")[0])
import capstone as cs
TEXT=(0x1000,0x7649000)
def disp_scan(disp):
    pat=disp.to_bytes(4,'little')
    hits={}
    start=TEXT[0]; end=TEXT[0]+TEXT[1]
    i=D.find(pat,start,end)
    cands=[]
    while i!=-1 and i<end:
        cands.append(i); i=D.find(pat,i+1,end)
    # adjudicate: try decoding from up to 15 bytes before, all alignments, keep any insn whose mem disp == disp and covers the bytes
    found={}
    for c in cands:
        for back in range(1,16):
            a=c-back
            if a<start: continue
            g=list(md.disasm(D[a:a+16],a))
            if not g: continue
            ins=g[0]
            if ins.address+ins.size<=c: continue
            ok=False
            for op in ins.operands:
                if op.type==cs.x86.X86_OP_MEM and op.mem.disp==disp: ok=True
            if ok:
                found.setdefault(ins.address,(ins.bytes.hex(),ins.mnemonic+' '+ins.op_str,ins.reg_name(ins.operands[0].mem.base) if ins.operands[0].type==cs.x86.X86_OP_MEM else '?'))
    return cands,found
for disp in (0x12B0,0x16C8,0x16B0):
    c,f=disp_scan(disp)
    print("\n=== disp %#x : %d byte candidates, %d decoded insns ==="%(disp,len(c),len(f)))
    for a in sorted(f):
        b,t,base=f[a]
        print("   %#010x %-24s %s"%(a,b,t))
