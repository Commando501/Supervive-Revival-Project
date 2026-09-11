import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,und,ind=cfg(I,0x035EC850); P=preds(succ)
print("Velocity base = this+0xE8 ; X@0xE8 Y@0xF0 Z@0xF8  (seed [M]).")
print("rdi == this (sole def 0x035EC87B mov rdi,rcx):", ins[0x035EC87B].mnemonic, ins[0x035EC87B].op_str)
rdidefs=[a for a in ins if any(ins[a].reg_name(r)=='rdi' for r in ins[a].regs_access()[1])]
print("all rdi defs in fn:", [(hex(a),ins[a].mnemonic,ins[a].op_str) for a in rdidefs])
print()
print("=== THE FOUR WRITES L2's [rsi] SCAN COULD NOT SEE — each is Velocity.Z ===")
for a in (0x35ecbd1,0x35ecbde,0x35ecfe2,0x35ed5ce):
    print("\n--- %08x ---" % a)
    ctx=[x for x in sorted(ins) if a-0x28<=x<=a+0x10]
    for x in ctx:
        i=ins[x]; mark=' <== WRITE Velocity.Z' if x==a else ''
        t=''
        for o in i.operands:
            if o.type==X86_OP_MEM and i.reg_name(o.mem.base)=='rip':
                t=' -> 0x%08X' % (i.address+i.size+o.mem.disp)
        print("   %08x %-20s %-8s %-38s%s%s" % (x,i.bytes.hex(),i.mnemonic,i.op_str,t,mark))
print()
print("=== does any lea alias rax onto the [rbp+0x168] temp? (L2's Q2 exhaustiveness) ===")
for a in sorted(ins):
    i=ins[a]
    if i.id==X86_INS_LEA and i.operands[1].type==X86_OP_MEM and i.reg_name(i.operands[1].mem.base)=='rbp':
        d=i.operands[1].mem.disp
        if 0x140<=d<=0x1A0: print("   %08x lea %s   <-- in range of the temp" % (a,i.op_str))
