import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
for a in (0x03600A1A,0x03600A21,0x03600A28,0x036009EE):
    pass
def riptarget(rva,end):
    r=[]
    for i in MD.disasm(D[rva:end], rva):
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                r.append((i.address,i.mnemonic,i.op_str,t))
    return r
for a,m,o,t in riptarget(0x036009BC,0x03600A40):
    print("%08X %s %s -> RVA %08X byte=%02X" % (a,m,o,t,D[t]))
    print("     wide: %r" % wstr(t,120))
    print("     ansi: %r" % cstr(t,80))
print()
print("engine CMC vtable 0x07FBED58 slot215(+0x6b8) =", hex(v2r(qq(0x07FBED58+0x6b8))))
print("loki   CMC vtable 0x088F8570 slot215(+0x6b8) =", hex(v2r(qq(0x088F8570+0x6b8))))
