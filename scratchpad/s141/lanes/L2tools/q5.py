import sys
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import cfg, fmt
from capstone.x86 import *
img=L2Img('dumps/merged14.dump.exe')
insns,succ,bad = cfg(img, 0x035EC850, 0x035EC000, 0x035EF000)
addrs=sorted(insns)

print("=== Q5a: is rdi provably `this`? every DEFINITION of rdi ===")
for a in addrs:
    i=insns[a]
    rr,rw=i.regs_access()
    if X86_REG_RDI in set(rw) or (i.operands and i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg)=='rdi'):
        print("   "+fmt(i))
print()

print("=== Q5b: EVERY write to Velocity (any [rsi+0..0x17] store) in engine PhysFalling ===")
vw=[]
for a in addrs:
    i=insns[a]
    if not i.operands: continue
    op=i.operands[0]
    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RSI and 0 <= op.mem.disp <= 0x18 and op.mem.index==0:
        vw.append(i)
for i in vw: print("   "+fmt(i)+"    [%d bytes at Velocity+0x%X]" % (i.operands[0].size, i.operands[0].mem.disp))
print("   total: %d Velocity stores" % len(vw))
print()

print("=== Q5c: the UPPER block 0x035ED906..0x035ED94E - is there a guard on its write? ===")
for a in [x for x in addrs if 0x035ED8F0 <= x <= 0x035ED960]:
    print("   "+fmt(insns[a]))
print()
print("   predecessors of 0x035ED946 (the upper movups [rsi]):")
preds=[a for a in addrs if 0x035ED946 in succ.get(a,[])]
for p in preds: print("      "+fmt(insns[p]))
print()

print("=== Q5d: predecessors of the zeroing store 0x035ED9AC and of 0x035ED9BB ===")
for tgt in (0x035ED998, 0x035ED9AC, 0x035ED9BB, 0x035ED9C8):
    preds=[a for a in addrs if tgt in succ.get(a,[])]
    print("   preds(0x%08X) = %s" % (tgt, ['0x%08X (%s %s)'%(p,insns[p].mnemonic,insns[p].op_str) for p in preds]))
print()

print("=== Q5e: who else in this function writes [rbp+0x168..0x17F]? (incl. via pointer escape) ===")
for a in addrs:
    i=insns[a]
    for k,op in enumerate(i.operands):
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RBP and 0x160<=op.mem.disp<=0x180:
            print("   "+fmt(i)+"   op%d disp=0x%X size=%d %s" % (k,op.mem.disp,op.size,"WRITE" if k==0 else "read/lea"))
