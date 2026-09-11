import sys, binascii
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
print("IMAGE:", IMG)
print("ImageBase %#x  FLAT=%s  sections=%d" % (im.imagebase, im.flat(), im.nsec))
ok = True
# DARK negative control
d = im.page_nonzero(0x5A6AC40)
print("[CTRL DARK] 0x5A6AC40 ULokiRespawnComponent::Respawn page_nonzero=%d/4096  %s" % (d, "PASS" if d==0 else "FAIL"))
ok &= (d==0)
folds = {0x0F7EC20:'c20000', 0x0F7EB50:'33c0c3', 0x0F7EB60:'32c0c3', 0x0B9E1F0:'b001c3', 0x0FC6CF0:'0f57c0c3'}
for rva, exp in folds.items():
    got = binascii.hexlify(im.read(rva, len(exp)//2)).decode()
    st = "PASS" if got==exp else "FAIL"
    print("[CTRL FOLD] %#09x exp=%s got=%s %s" % (rva, exp, got, st))
    ok &= (got==exp)
# LIT positive controls relevant to lane: GAS-ish + CMC
pos = {
 0x055AC9F0: "ULokiCMC +0xC00 GAS attribute slot",
 0x055B89F0: "ULokiCMC::PhysFalling",
 0x035EC850: "engine PhysFalling",
 0x03BBD9F0: "APawn::SetPlayerState",
}
for rva, name in pos.items():
    n = im.page_nonzero(rva)
    print("[CTRL LIT ] %#09x %-40s page_nonzero=%d/4096 %s" % (rva, name, n, "PASS" if n>0 else "FAIL"))
    ok &= (n>0)
print("CONTROLS:", "ALL PASS" if ok else "*** FAILURE ***")
