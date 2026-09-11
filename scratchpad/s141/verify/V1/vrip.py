import struct, capstone
from capstone import x86
from vimg import VImg
im=VImg()
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
def ripterm(rva):
    b=im.read(rva,16)
    i=next(CS.disasm(b,rva))
    for o in i.operands:
        if o.type==x86.X86_OP_MEM and o.mem.base==capstone.x86.X86_REG_RIP:
            tgt=rva+i.size+o.mem.disp
            return i, tgt
    return i, None
print("\n=== RIP-relative targets recomputed BY MACHINE ===")
for rva,note in [(0x035d6511,'CalcVelocity movups xmm1 (candidate ZeroVector XY)'),
                 (0x035d6518,'CalcVelocity movsd xmm2  (candidate Zero Z)'),
                 (0x035ED98E,'THE SizeSq2D GATE comisd'),
                 (0x035ED934,'Q4 movss xmm13 constant'),
                 (0x035EC873,'MIN_TICK_TIME comiss constant')]:
    i,t=ripterm(rva)
    print(f" {rva:#010x} {i.bytes.hex():22s} {i.mnemonic} {i.op_str}")
    if t is None: print("     (no rip operand)"); continue
    sec=[s[0] for s in im.secs if s[1]<=t<s[1]+max(s[2],s[4])]
    raw=im.read(t,16)
    print(f"     -> target {t:#010x} in {sec} bytes={raw.hex()}")
    print(f"        as f64 x2 : {struct.unpack('<dd',raw)}")
    print(f"        as f32 x4 : {struct.unpack('<ffff',raw)}")
