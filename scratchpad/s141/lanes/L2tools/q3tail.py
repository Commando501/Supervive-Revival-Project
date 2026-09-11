import sys
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
from l2dis import cfg, fmt
from capstone.x86 import *
img=L2Img('dumps/merged14.dump.exe')
for ent,nm,q in [(0x035F4620,'helper A',0x1F0),(0x035F4770,'helper B',0x210)]:
    insns,succ,bad=cfg(img,ent,ent-0x10,ent+0x200)
    addrs=sorted(insns)
    print("=== %s 0x%08X : %d insns, %d undecodable, extent 0x%08X..0x%08X ===" %
          (nm,ent,len(insns),len(bad),addrs[0],addrs[-1]))
    # writes through rax/rdx (the OUT buffer)
    print("  -- stores through the OUT pointer --")
    tot=0
    for a in addrs:
        i=insns[a]
        if not i.operands: continue
        op=i.operands[0]
        if op.type==X86_OP_MEM and op.mem.base in (X86_REG_RAX,X86_REG_RDX) and op.mem.disp<0x40:
            print("     "+fmt(i)+"   [%d bytes at OUT+0x%X]" % (op.size,op.mem.disp)); tot+=op.size
    print("     total bytes written through OUT: %d" % tot)
    print("  -- reads of the quat [rcx+...] and the IN vector [r8+...] --")
    for a in addrs:
        i=insns[a]
        for k,op in enumerate(i.operands):
            if op.type==X86_OP_MEM and op.mem.base in (X86_REG_RCX,X86_REG_R8):
                reg=i.reg_name(op.mem.base)
                print("     "+fmt(i)+"   [%s+0x%X] %d bytes" % (reg,op.mem.disp,op.size))
    print("  -- rax definitions (does it return the OUT buffer?) --")
    for a in addrs:
        i=insns[a]
        if i.operands and i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg)=='rax':
            print("     "+fmt(i))
    rets=[a for a in addrs if insns[a].id==X86_INS_RET]
    print("  -- ret at: %s" % ['0x%08X'%a for a in rets])
    print()
