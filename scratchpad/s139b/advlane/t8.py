import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("xmm11 const at 0x035ECBFC:")
for i in MD.disasm(D[0x035ECBFC:0x035ECC05],0x035ECBFC):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            t=i.address+i.size+op.mem.disp
            print("   -> RVA %08X  qword=%016X  (sign mask 0x8000000000000000? %s)"%(t,qq(t),qq(t)==0x8000000000000000))
print()
print("=== rsi definition search in 0x035EC887..0x035ECCF8 ===")
for i in MD.disasm(D[0x035EC887:0x035ECCF8],0x035EC887):
    if i.mnemonic in ('lea','mov','xor') and i.operands and i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg)=='rsi':
        print("  %08X  %s %s"%(i.address,i.mnemonic,i.op_str))
print()
print("=== ALL conditional branches 0x035EC881..0x035ECCF0 with targets ===")
for i in MD.disasm(D[0x035EC850:0x035ECCF8],0x035EC850):
    if i.group(CS_GRP_JUMP):
        tgt = i.operands[0].imm if i.operands[0].type==X86_OP_IMM else None
        fwd = ''
        if tgt is not None and tgt > 0x035ECCEF: fwd=' *** SKIPS PAST NewFallVelocity ***'
        print("  %08X %-6s %s%s"%(i.address,i.mnemonic,i.op_str,fwd))
