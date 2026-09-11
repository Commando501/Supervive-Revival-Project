import struct
from vimg import VImg
im=VImg(); IB=im.imagebase
def slot(vt,disp):
    v=struct.unpack_from('<Q',im.read(vt+disp,8),0)[0]
    return v, (v-IB) if v>IB else None
print("=== VTABLE DERIVATION (independent of lane) ===")
for vtname,vt in [("ULokiCMC .rdata 0x088F8570",0x088F8570),("engine CMC .rdata 0x07FBED58",0x07FBED58)]:
    print(f"\n{vtname}")
    for disp,nm in [(0x830,'PhysFalling'),(0x7A0,'NewFallVelocity'),(0x7B0,'CalcVelocity'),
                    (0x4C0,'GetGravityZ'),(0x4C8,'GetMaxSpeed'),(0x7D0,'GetMaxAcceleration'),
                    (0x660,'ComputeAnalogInputModifier'),(0x720,'StartNewPhysics'),(0xA50,'(clears +0x16C8)'),
                    (0xCE0,'?disp0xCE0'),(0x6B8,'HasValidData?')]:
        v,r=slot(vt,disp)
        pz = im.pnz(r) if r and r<0x7649000 else -1
        print(f"  disp {disp:#06x} {nm:28s} VA={v:#018x} RVA={r:#010x} page={pz}/4096")
