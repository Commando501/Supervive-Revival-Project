from v import im
FOLDS={0x0F7EC20:'c20000',0x0F7EB50:'33c0c3',0x0F7EB60:'32c0c3',0x0B9E1F0:'b001c3',0x0FC6CF0:'0f57c0c3'}
print("== FOLD CONSTANTS ==")
ok=True
for rva,exp in FOLDS.items():
    got=im.read(rva,len(exp)//2).hex()
    st = 'PASS' if got==exp else '*** FAIL'
    ok &= got==exp
    print(f"  {rva:#09x} expect {exp:<10s} got {got:<10s} {st}")
print("== DARK NEGATIVE CONTROL ==")
d=im.page_nonzero(0x5A6AC40)
print(f"  0x5A6AC40 ULokiRespawnComponent::Respawn page_nonzero = {d}/4096  {'PASS' if d==0 else '*** FAIL'}")
print("== LIT POSITIVE CONTROLS ==")
for name,rva in [("ENGINE PhysFalling",0x035EC850),("ULokiCMC::PhysFalling",0x055B89F0),
                 ("ULokiCMC::StartNewPhysics",0x055C2430),("ENGINE StartNewPhysics",0x03600990),
                 ("ENGINE CalcVelocity",0x035D5D20),("ENGINE PerformMovement",0x035E9EC0),
                 ("ULokiCMC::PerformMovement",0x055B8370),
                 ("HPL loki 0x55AEB60",0x055AEB60),("HPL engine 0x35E60F0",0x035E60F0),
                 ("Launch 0x35E7340",0x035E7340),("AddImpulse eng 0x35D1E00",0x035D1E00),
                 ("GetGravityZ loki 0x55AB8C0",0x055AB8C0),("NewFallVel loki 0x55B6AD0",0x055B6AD0),
                 ("PhysCustom loki 0x55B88E0",0x055B88E0)]:
    n=im.page_nonzero(rva)
    print(f"  {rva:#09x} {name:<32s} {n:5d}/4096 {'PASS' if n>0 else '*** DARK'}")
# .text page census / denominator
tx=[s for s in im.sections if s['name']=='.text'][0]
npages=tx['vsz']//0x1000
lit=0
data=im.data
for p in range(npages):
    off=tx['praw']+p*0x1000
    if any(data[off:off+0x1000]): lit+=1
print(f"== DENOMINATOR ==  .text pages {npages}  lit {lit}  = {100.0*lit/npages:.2f}%")
