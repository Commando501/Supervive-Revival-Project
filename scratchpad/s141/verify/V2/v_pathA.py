import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,undec,indir=cfg(I,0x035EC850); P=preds(succ)
print("PATH A buffer = [rbp+0x2b0] (lea at 035ed8ec). Its three slots:")
for a in (0x035ED8DE,0x035ED8F3,0x035ED8FB):
    i=ins[a]; o=i.operands[0]
    print("   %08x %-22s %-7s %-38s  -> [rbp+0x%x] = slot +0x%x" % (a,i.bytes.hex(),i.mnemonic,i.op_str,o.mem.disp,o.mem.disp-0x2b0))
print("PATH B buffer = [rbp+0x2c8] (lea at 035ed909). Its three slots:")
for a in (0x035ED918,0x035ED920,0x035ED928):
    i=ins[a]; o=i.operands[0]
    print("   %08x %-22s %-7s %-38s  -> slot +0x%x" % (a,i.bytes.hex(),i.mnemonic,i.op_str,o.mem.disp-0x2c8))
print()
print("PATH A sources: xmm6=[rsi](Vel.X) subsd xmm13 ; xmm7=[rsi+8](Vel.Y) subsd xmm12 ; +0x10=xmm8")
print("PATH B sources: [rsi](Vel.X) ; [rdi+0xf0](Vel.Y) ; xmm8")
print()
print("Guards selecting between them:")
for a in (0x035ED8C7,0x035ED8D7):
    i=ins[a]; print("   %08x %s %s   (taken -> 0x35ed905 = PATH B; fallthrough -> PATH A)" % (a,i.mnemonic,i.op_str))
print()
# DOMINANCE: does 0x035ED8EC dominate 0x035ED946?
tgt=0x035ED946
for rm,label in [(0x035ED909,"lea rax,[rbp+0x2c8] (path B)"),(0x035ED8EC,"lea rax,[rbp+0x2b0] (path A)"),
                 (0x035EC9AC,"lea rsi,[rdi+0xe8]")]:
    r=reach(succ,0x035EC850,frozenset([rm]))
    print("   remove %08x %-34s -> reachable %4d ; 0x035ED946 reachable: %s" % (rm,label,len(r),tgt in r))
