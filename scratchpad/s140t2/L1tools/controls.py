import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
pe = load()
print("=== L1 OWN CONTROLS (independent code) ===")
print("PE flat (VA==raw for all sections):", pe.flat)
print("ImageBase: 0x%X" % pe.imagebase)
print()
print("-- C1: known-DARK control (CLAUDE.md: ULokiRespawnComponent::Respawn 0x5A6AC40 still dark in merged13)")
nz = pe.page_nonzero(0x5A6AC40)
print("   page 0x%08X non-zero bytes = %d / 4096   %s" % (0x5A6AC40 & ~0xFFF, nz, "PASS(dark)" if nz==0 else "FAIL"))
print()
print("-- C2: fold constants byte-exact")
folds = {0x0F7EC20:'c20000', 0x0F7EB50:'33c0c3', 0x0F7EB60:'32c0c3', 0x0B9E1F0:'b001c3', 0x0FC6CF0:'0f57c0c3'}
ok=0
for rva, want in folds.items():
    got = pe.read(rva, len(want)//2).hex()
    good = got == want
    ok += good
    print("   0x%07X  got %-10s want %-10s %s" % (rva, got, want, "PASS" if good else "FAIL"))
print("   %d/%d PASS" % (ok, len(folds)))
print()
print("-- C3: ULokiCMC vtable .rdata 0x088F8570 displacements (expect Loki bodies)")
VT_LOKI = 0x088F8570
VT_ENG  = 0x07FBED58
for disp, want, label in [(0xAA8,0x055B8370,'ULokiCMC::PerformMovement'),
                          (0x720,0x055C2430,'ULokiCMC::StartNewPhysics'),
                          (0xA50,0x0530ABF0,'disp 0xA50 (the clear)'),
                          (0x830,0x055B89F0,'PhysFalling'),
                          (0x6B8,0x035E64C0,'HasValidData (engine body)')]:
    p = pe.u64(VT_LOKI+disp); rva = p - pe.imagebase
    print("   LokiVT+0x%03X -> 0x%016X  rva 0x%07X  want 0x%07X  %s  [%s]" % (disp, p, rva, want, "PASS" if rva==want else "FAIL", label))
print("-- C4: engine UCMC vtable .rdata 0x07FBED58 (two-sided control)")
for disp, want, label in [(0xAA8,0x035E9EC0,'engine PerformMovement'),
                          (0x720,0x03600990,'engine StartNewPhysics'),
                          (0xA50,0x035D6790,'engine disp 0xA50')]:
    p = pe.u64(VT_ENG+disp); rva = p - pe.imagebase
    print("   EngVT +0x%03X -> 0x%016X  rva 0x%07X  want 0x%07X  %s  [%s]" % (disp, p, rva, want, "PASS" if rva==want else "FAIL", label))
print()
print("-- C5: LIT check on functions under analysis")
for rva,label in [(0x055C2430,'ULokiCMC::StartNewPhysics'),(0x035EB13A,'engine PM call site'),
                  (0x0530ABF0,'disp 0xA50 clear'),(0x0530AC10,'GetRecentVelocity impl'),
                  (0x0559E180,'ALokiChar ctor(?)'),(0x0559F580,'ULokiCMC ctor(?)'),
                  (0x035E9EC0,'engine PerformMovement')]:
    print("   0x%07X page nz=%4d  [%s]" % (rva, pe.page_nonzero(rva), label))
