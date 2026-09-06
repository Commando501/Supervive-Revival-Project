import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X=capstone.x86
im=Img()
LOGGER=0x0106B650
tests=[(0x035d8b70,'ClearAccumulatedForces (CMC vt+0x810)'),
       (0x03786fa0,'~FScopedMovementUpdate (0x3786fa0)'),
       (0x037dd080,'RootMotionGroup HasActiveSources'),
       (0x037c8250,'RootMotionGroup Clear'),
       (0x03536040,'ACharacter::IsPlayingRootMotion'),
       (0x03603640,'TickCharacterPose (CMC vt+0xb68)')]
for rva,name in tests:
    try:
        c=CFG(im,rva,maxinsn=30000)
    except Exception as e:
        print(f"  {name}: CFG failed {e}"); continue
    direct=[t for t in c.calls.values() if t is not None]
    has=LOGGER in direct
    rip=0
    for r,i in c.insns.items():
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP: rip+=1
    print(f"  {rva:#010x} {name:<42s} insns={len(c.insns):5d} calls={len(c.calls):3d} riprefs={rip:3d} calls-logger={has} indirect_jmps={len(c.indirect_jumps)}")
