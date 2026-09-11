import io,sys,struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
for a,e in ((0x055B8E9D,0x055B8EA6),(0x055B8EAD,0x055B8EB4),(0x055B8EB4,0x055B8EBB),(0x055B8F1B,0x055B8F22),(0x055B9001,0x055B9009),(0x055B8FA9,0x055B8FB1)):
    for i in MD.disasm(D[a:e],a):
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                print("%08X %-8s %-40s -> RVA %08X  q=%016X  f32=%r f64=%r"%(i.address,i.mnemonic,i.op_str,t,qq(t),ff(t),struct.unpack_from('<d',D,t)[0]))
print()
print("=== engine NewFallVelocity 0x035E8B00 (page nz=%d) ==="%pnz(0x035E8B00))
dump(0x035E8B00,0x035E8B95)
