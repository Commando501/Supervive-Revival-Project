import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
print("IMAGE:", IMG)
print(f"ImageBase {im.imagebase:#x} SizeOfImage {im.sizeofimage:#x} nsec {im.nsec}")
print("FLAT (va==praw all sections):", im.flat())
for s in im.sections:
    print(f"  {s['name']:10s} va={s['va']:#010x} praw={s['praw']:#010x} vsz={s['vsz']:#010x} rawsz={s['rawsz']:#010x} {'FLAT' if s['va']==s['praw'] else '*** NOT FLAT ***'}")

print("\n--- MANDATORY CONTROLS ---")
ok = True
# DARK negative control
nz = im.page_nonzero(0x5A6AC40)
print(f"[C1] DARK ctrl ULokiRespawnComponent::Respawn 0x5A6AC40 page_nonzero = {nz}/4096  expect 0  -> {'PASS' if nz==0 else 'FAIL'}")
ok &= (nz==0)
# fold constants
folds = {0x0F7EC20:'c20000', 0x0F7EB50:'33c0c3', 0x0F7EB60:'32c0c3', 0x0B9E1F0:'b001c3', 0x0FC6CF0:'0f57c0c3'}
for rva,exp in folds.items():
    got = im.read(rva, len(exp)//2).hex()
    r = got==exp
    ok &= r
    print(f"[C2] fold {rva:#09x} expect {exp:10s} got {got:10s} -> {'PASS' if r else 'FAIL'}")
# LIT positive controls relevant to lane
pos = {
 0x035EC850:'ENGINE PhysFalling (my entry)',
 0x055B89F0:'ULokiCMC::PhysFalling',
 0x03600990:'ENGINE StartNewPhysics',
 0x035D5D20:'ENGINE CalcVelocity',
 0x035E9EC0:'ENGINE PerformMovement',
 0x035F4620:'quat rot A (gravity->world)',
 0x035F4770:'quat rot B (world->gravity)',
}
for rva,name in pos.items():
    nz = im.page_nonzero(rva)
    b = im.read(rva,8).hex()
    r = nz>0
    ok &= r
    print(f"[C3] LIT {rva:#09x} {name:32s} page {nz:4d}/4096 first8={b} -> {'PASS' if r else 'FAIL'}")
# the gate constant
import struct
gc = im.read(0x077F5180, 8)
val = struct.unpack('<d', gc)[0]
print(f"\n[C4] gate const .rdata 0x077F5180 bytes={gc.hex()} double={val!r}")
import numpy as _n
print(f"      (double)(float)1e-4*10 = {float(_n.float32(1e-4))*10.0!r}")
print(f"      (double)(float)1e-3    = {float(_n.float32(1e-3))!r}")
print("\nCONTROLS:", "ALL PASS" if ok else "*** FAILURE -- STOP ***")
