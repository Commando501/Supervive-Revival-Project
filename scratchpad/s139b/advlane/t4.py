exec(open('H.py').read())
dump(0x036009BC, 0x03600A60)
print()
for i in MD.disasm(D[0x036009BC:0x03600A60], 0x036009BC):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            t=i.address+i.size+op.mem.disp
            print("  %08X %s %s  -> RVA %08X  byte=%02X  wstr=%r  cstr=%r" % (i.address,i.mnemonic,i.op_str,t,D[t], wstr(t,80), cstr(t,60)))
