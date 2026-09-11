import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("calls to StartNewPhysics (direct 0x3600990 / vtbl +0x720) inside engine PhysFalling:")
for i in MD.disasm(D[0x035EC850:0x035EE593],0x035EC850):
    if i.group(CS_GRP_CALL):
        op=i.operands[0]
        if op.type==X86_OP_IMM and op.imm==0x3600990: print("  DIRECT %08X"%i.address)
        if op.type==X86_OP_MEM and op.mem.disp in (0x720,):
            print("  VTBL+0x720 %08X %s"%(i.address,i.op_str))
print()
print("all indirect vtable calls in engine PhysFalling (disp):")
s={}
for i in MD.disasm(D[0x035EC850:0x035EE593],0x035EC850):
    if i.group(CS_GRP_CALL):
        op=i.operands[0]
        if op.type==X86_OP_MEM: s.setdefault(op.mem.disp,[]).append(i.address)
for d in sorted(s): print("  +0x%-5X n=%d  slot=%d  first=%08X"%(d,len(s[d]),d//8,s[d][0]))
print()
print("writes to [rsi] (=&Velocity) in engine PhysFalling:")
for i in MD.disasm(D[0x035EC850:0x035EE593],0x035EC850):
    if i.operands and i.operands[0].type==X86_OP_MEM and i.operands[0].mem.base==X86_REG_RSI and i.mnemonic.startswith('mov'):
        print("  %08X %s %s"%(i.address,i.mnemonic,i.op_str))
