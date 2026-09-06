import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone, struct
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
for ent,label in [(0x035F4620,'0x35F4620  (called with OUT=rdx, IN=r8) -- used as RotateGravityToWorld'),
                  (0x035F4770,'0x35F4770  (called with OUT=rdx, IN=r8) -- used as RotateWorldToGravity')]:
    c=CFGMOD.CFG(im,ent); ins=c.insns
    print(f"\n================ {label} ================")
    print(f"  insns={len(ins)} calls={len(c.calls)} indirect_jmp={len(c.indirect_jumps)} decfail={len(c.decode_failures)}")
    for r in sorted(ins):
        i=ins[r]
        ex=''
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
                t=r+i.size+op.mem.disp
                try:
                    b=im.read(t,8); ex=f"  ; ->{t:#x} d={struct.unpack('<d',b)[0]!r}"
                except Exception: ex=f"  ; ->{t:#x}"
        print(f"  {r:#010x}  {bytes(i.bytes).hex():22s} {i.mnemonic:9s} {i.op_str}{ex}")
print("\n=== are they byte-identical (ICF-folded)? ===")
a=im.read(0x035F4620,0x150); b=im.read(0x035F4770,0x150)
print("  identical:", a==b)
if a!=b:
    diffs=[k for k in range(len(a)) if a[k]!=b[k]]
    print(f"  first differing byte offsets: {diffs[:20]}  (n={len(diffs)})")
    for k in diffs[:12]:
        print(f"    +{k:#x}: A={a[k]:#04x} B={b[k]:#04x}")
