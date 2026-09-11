exec(open('H.py').read())
# machine-recompute every rip-relative and rel32 in engine PhysFalling head
for i in MD.disasm(D[0x035EC850:0x035EC890], 0x035EC850):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            t=i.address+i.size+op.mem.disp
            print("%08X %s %s -> rip target RVA %08X  dword=%08X  f32=%r" % (i.address,i.mnemonic,i.op_str,t,dd(t),ff(t)))
    if i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL):
        print("%08X %s %s   (target parsed by capstone)" % (i.address,i.mnemonic,i.op_str))
print()
print("KINDA/MIN_TICK candidates: 1e-6 float bits =", hex(struct.unpack('<I',struct.pack('<f',1e-6))[0]))
# StartNewPhysics engine guard
print('--- engine StartNewPhysics 0x03600990 head ---')
dump(0x03600990, 0x036009D8)
for i in MD.disasm(D[0x03600990:0x036009D8], 0x03600990):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            t=i.address+i.size+op.mem.disp
            print("   rip -> RVA %08X dword=%08X f32=%r" % (t,dd(t),ff(t)))
