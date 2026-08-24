import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
for name,e in [("A 0x035F4620",0x035F4620),("B 0x035F4770",0x035F4770)]:
    ins,succ,und,ind=cfg(I,e); P=preds(succ)
    lo=min(ins); hi=max(a+ins[a].size for a in ins)
    rets=[a for a in ins if ins[a].id in RETS]
    calls=[a for a in ins if ins[a].id==X86_INS_CALL]
    raxdef=[a for a in ins if any(ins[a].reg_name(r) in('rax','eax') for r in ins[a].regs_access()[1])]
    print("%s: insns=%d und=%d ind=%d extent %08x..%08x rets=%s calls=%d" % (name,len(ins),len(und),len(ind),lo,hi,[hex(x) for x in rets],len(calls)))
    print("   rax defs:", [(hex(a),ins[a].mnemonic,ins[a].op_str) for a in raxdef])
    rcx=sorted({ins[a].operands[1].mem.disp for a in ins
                if len(ins[a].operands)>1 and ins[a].operands[1].type==X86_OP_MEM
                and ins[a].reg_name(ins[a].operands[1].mem.base)=='rcx'})
    r8=sorted({ (ins[a].operands[1].mem.disp, ins[a].operands[1].size) for a in ins
                if len(ins[a].operands)>1 and ins[a].operands[1].type==X86_OP_MEM
                and ins[a].reg_name(ins[a].operands[1].mem.base)=='r8'})
    wr=sorted({ (ins[a].operands[0].mem.disp, ins[a].operands[0].size) for a in ins if mem_writes(ins[a]) is not None
                and ins[a].reg_name(ins[a].operands[0].mem.base)=='rdx'})
    print("   reads [rcx+d]:", [hex(x) for x in rcx])
    print("   reads [r8+d]:", [(hex(d),s) for d,s in r8], "  writes [rdx+d]:", [(hex(d),s) for d,s in wr])
    print()
a=I.read(0x035F4620,0x14F); b=I.read(0x035F4770,0x14F)
diff=[i for i in range(len(a)) if a[i]!=b[i]]
print("byte diff over %d bytes: %d differing at offsets %s" % (len(a),len(diff),[hex(x) for x in diff]))
for o in diff: print("    +0x%03x: A=%02x B=%02x  (delta %+d)" % (o,a[o],b[o],b[o]-a[o]))
