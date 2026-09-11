import capstone
from capstone import x86
from vimg import VImg
from vcfg import G
im=VImg()
for entry,nm in [(0x035D5D20,'engine CalcVelocity'),(0x035E8B00,'engine NewFallVelocity')]:
    g=G(im,entry)
    print(f"\n=== {nm} {entry:#x}: {len(g.I)} insns, {len(g.calls)} calls, {len(g.ijmp)} ijmp, {len(g.fail)} fail ===")
    # find writes to [reg+0xe8]/[reg+0xf0]/[reg+0xf8] -- candidate Velocity writes on 'this'
    for a in sorted(g.I):
        i=g.I[a]
        if not i.operands: continue
        o=i.operands[0]
        if o.type!=x86.X86_OP_MEM: continue
        if i.mnemonic in ('cmp','test','push','call','jmp'): continue
        if o.mem.disp in (0xe8,0xf0,0xf8) and o.mem.base:
            print(f"   {a:#010x} {i.bytes.hex():22s} {i.mnemonic:8s} {i.op_str}")
