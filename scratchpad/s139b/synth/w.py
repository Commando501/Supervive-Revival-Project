import struct, capstone, re
P=r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
d=open(P,'rb').read()
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
TS,TE=0x1000,0x1000+124030976
def scan(disp):
    pat=struct.pack('<I',disp)
    out=[]
    i=TS
    while True:
        i=d.find(pat,i,TE)
        if i<0: break
        for back in range(1,16):
            a=i-back
            try: ins=next(md.disasm(d[a:a+16],a,count=1))
            except StopIteration: continue
            if ins.size>back and ins.address+ins.size>i:
                # check disp actually equals
                ok=False
                for op in ins.operands:
                    if op.type==capstone.x86.X86_OP_MEM and op.mem.disp==disp: ok=True
                if ok: out.append(ins)
                break
        i+=1
    return out
for disp,label in ((0x12B0,'+0x12B0'),(0x16C8,'+0x16C8')):
    print("==== disp %s ===="%label)
    seen=set()
    for ins in scan(disp):
        if ins.address in seen: continue
        seen.add(ins.address)
        # writes only? print all, mark write
        w='  '
        if ins.mnemonic in ('mov','movss','movsd','movups','movaps','add','and','or','xor') and ins.op_str.startswith(('dword','qword','byte','word','xmmword')):
            w='W '
        print("%s%08X %-8s %s"%(w,ins.address,ins.mnemonic,ins.op_str))
