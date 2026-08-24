import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
print("IMAGE:", IMG)
print("FLAT:", im.flat(), " ImageBase", hex(im.imagebase))
ok = True

# --- DARK negative control
d = im.page_nonzero(0x5A6AC40)
print(f"[CTRL-DARK] 0x5A6AC40 ULokiRespawnComponent::Respawn page_nonzero = {d}/4096  -> {'PASS (dark)' if d==0 else 'FAIL'}")
ok &= (d==0)

# --- fold constants
folds = {
 0x0F7EC20: 'c20000',
 0x0F7EB50: '33c0c3',
 0x0F7EB60: '32c0c3',
 0x0B9E1F0: 'b001c3',
 0x0FC6CF0: '0f57c0c3',
}
for rva, want in folds.items():
    got = im.read(rva, len(want)//2).hex()
    st = 'PASS' if got == want else 'FAIL'
    print(f"[CTRL-FOLD] {rva:#09x} want {want} got {got}  {st}")
    ok &= (got==want)

# --- LIT positive controls relevant to L5
pos = {
 0x035EC850: 'ENGINE PhysFalling',
 0x055B89F0: 'ULokiCMC::PhysFalling',
 0x055C2430: 'ULokiCMC::StartNewPhysics',
 0x035D5D20: 'ENGINE CalcVelocity',
 0x055B6AD0: 'ULokiCMC::NewFallVelocity',
 0x055AB8C0: 'ULokiCMC::GetGravityZ',
 0x0530ABF0: 'ULokiCMC disp 0xA50 (clears +0x16C8)',
 0x055AC9F0: 'GAS +0xC00 slot',
}
for rva, nm in pos.items():
    n = im.page_nonzero(rva)
    print(f"[CTRL-LIT ] {rva:#09x} {nm:38s} page_nonzero={n}/4096 {'PASS (lit)' if n>0 else 'FAIL (dark!)'}")
    ok &= (n>0)

print()
print("ALL CONTROLS:", "PASS" if ok else "*** FAIL ***")
