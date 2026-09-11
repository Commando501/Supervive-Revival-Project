import io,sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
exec(open('H.py').read())
print("=== Loki NewFallVelocity 0x055B6AD0 (page nz=%d) ==="%pnz(0x055B6AD0))
dump(0x055B6AD0,0x055B6B40)
print()
print("=== Loki TickComponent 0x055C2B90 head + HitStop 0x055C2BF0..0x055C2C40 (page nz=%d) ==="%pnz(0x055C2B90))
dump(0x055C2BF0,0x055C2C40)
for i in MD.disasm(D[0x055C2BF0:0x055C2C40],0x055C2BF0):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            print("    %08X -> RVA %08X"%(i.address, i.address+i.size+op.mem.disp))
