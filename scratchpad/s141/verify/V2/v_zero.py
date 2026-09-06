import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,undec,indir = cfg(I, 0x035EC850)
P = preds(succ)
print("=== CFG-ordered listing 0x035ED8F0..0x035ED9E0 ===")
for a in sorted(ins):
    if 0x035ED8F0 <= a <= 0x035ED9E0:
        i=ins[a]
        pr = sorted(P.get(a,()))
        print("%08x  %-26s %-8s %-42s preds=%s" % (a, i.bytes.hex(), i.mnemonic, i.op_str,
              '{'+','.join('%x'%x for x in pr)+'}' if len(pr)!=1 else '%x'%pr[0]))
print()
print("=== the store at 0x035ED9AC, decoded ===")
i=ins[0x035ED9AC]
print("bytes:", i.bytes.hex(), " ->", i.mnemonic, i.op_str)
o=i.operands[0]
print("op0.type==MEM:", o.type==X86_OP_MEM, " op0.size:", o.size, " base:", i.reg_name(o.mem.base), " disp: 0x%x"%o.mem.disp)
print("op1:", i.reg_name(i.operands[1].reg))
print()
print("=== the gate at 0x035ED98E ===")
i=ins[0x035ED98E]
print("bytes:", i.bytes.hex(), "->", i.mnemonic, i.op_str, " size", i.size)
tgt = i.address + i.size + i.operands[1].mem.disp
print("  rip-relative target = 0x%08X (recomputed by machine)" % tgt)
print("  capstone reports op1.size =", i.operands[1].size, " <- ISA says COMISD reads m64")
i=ins[0x035ED996]; print("gate branch:", hex(i.address), i.bytes.hex(), i.mnemonic, i.op_str)
