from vimg import VImg
im=VImg()
print("=== MANDATORY CONTROLS (merged14) ===")
d=im.pnz(0x5A6AC40); print(f"DARK ctrl 0x5A6AC40 page_nonzero = {d}/4096  {'PASS' if d==0 else 'FAIL'}")
folds={0x0F7EC20:'c20000',0x0F7EB50:'33c0c3',0x0F7EB60:'32c0c3',0x0B9E1F0:'b001c3',0x0FC6CF0:'0f57c0c3'}
for a,exp in folds.items():
    got=im.read(a,len(exp)//2).hex()
    print(f"fold {a:#09x} expect {exp:10s} got {got:10s} {'PASS' if got==exp else '*** FAIL ***'}")
for a,nm in [(0x035EC850,'engine PhysFalling'),(0x055B89F0,'ULokiCMC::PhysFalling'),
             (0x03600990,'engine StartNewPhysics'),(0x035D5D20,'engine CalcVelocity'),
             (0x035F4620,'quat helper A'),(0x035F4770,'quat helper B'),
             (0x035E9EC0,'engine PerformMovement'),(0x055C2430,'ULokiCMC::StartNewPhysics')]:
    print(f"LIT ctrl {a:#09x} {nm:28s} {im.pnz(a)}/4096")
