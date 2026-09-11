import sys; sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
img = L2Img('dumps/merged14.dump.exe')
print("=== MANDATORY CONTROLS (L2, independent reader) ===")
print("[C0] flat:", img.is_flat(), " imagebase 0x%X" % img.imagebase)

# DARK negative control
nz = img.page_nonzero(0x5A6AC40)
print("[C1] DARK ctrl ULokiRespawnComponent::Respawn 0x5A6AC40 page_nonzero = %d/4096  -> %s"
      % (nz, "PASS (dark)" if nz==0 else "*** FAIL ***"))

folds = {
 0x0F7EC20: 'c20000',
 0x0F7EB50: '33c0c3',
 0x0F7EB60: '32c0c3',
 0x0B9E1F0: 'b001c3',
 0x0FC6CF0: '0f57c0c3',
}
ok=True
for rva,exp in folds.items():
    got = img.read(rva, len(exp)//2).hex()
    st = "PASS" if got==exp else "*** FAIL ***"
    if got!=exp: ok=False
    print("[C2] fold 0x%07X expect %-10s got %-10s %s" % (rva, exp, got, st))

# LIT positive controls relevant to L2's lane
pos = {
 0x035EC850: 'ENGINE PhysFalling',
 0x035ED973: 'the SizeSq2D block (inside engine PhysFalling)',
 0x035F4620: 'quat helper A',
 0x035F4770: 'quat helper B',
 0x055B89F0: 'ULokiCMC::PhysFalling',
 0x035D5D20: 'ENGINE CalcVelocity',
}
for rva,nm in pos.items():
    n = img.page_nonzero(rva)
    print("[C3] LIT ctrl 0x%07X %-46s page_nonzero=%4d/4096 %s" % (rva,nm,n,"PASS" if n>0 else "*** FAIL ***"))

# .rdata page holding the gate constant
n = img.page_nonzero(0x077F5180)
print("[C4] .rdata 0x077F5180 page_nonzero=%d/4096 sect=%s" % (n, img.sect_of(0x077F5180)['name']))
