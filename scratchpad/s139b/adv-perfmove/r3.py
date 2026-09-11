from advh import *
TEXT_B,TEXT_E=0x1000,0x1000+0x07649000
def scan_disp(disp):
    pat=struct.pack('<I',disp)
    hits=[]
    p=TEXT_B
    while True:
        p=DATA.find(pat,p,TEXT_E)
        if p<0: break
        for back in range(3,11):
            a=p-back
            g=list(md.disasm(DATA[a:a+16],a))
            if not g: continue
            i=g[0]
            if i.address+i.size==p+4 or (i.address<p and i.address+i.size>=p+4):
                ok=False
                for op in i.operands:
                    if op.type==X86_OP_MEM and op.mem.disp==disp and op.mem.base!=X86_REG_RIP:
                        ok=True
                if ok:
                    hits.append((a,i))
                    break
        p+=1
    return hits
for disp,name in ((0x12B0,'+0x12B0'),(0x16D0,'+0x16D0'),(0x16C8,'+0x16C8')):
    hits=scan_disp(disp)
    print("=== %s : %d candidate instructions"%(name,len(hits)))
    for a,i in hits:
        # is it a WRITE (mem is dest)?
        w = i.mnemonic in ('mov','movss','movsd','movups','movaps','add','sub','or','and','inc','dec') and i.op_str.strip().startswith(('dword','qword','byte','word','xmmword'))
        print("   %-5s 0x%08X %-42s"%("WRITE" if w else "read",a,i.mnemonic+" "+i.op_str))
