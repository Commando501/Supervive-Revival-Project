import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
print("IMAGE:", IMG)
print("ImageBase %#x  FLAT=%s  nsec=%d" % (im.imagebase, im.flat(), im.nsec))
for s in im.sections:
    print("  %-10s va=%#010x praw=%#010x vsz=%#010x rawsz=%#010x %s" % (
        s['name'], s['va'], s['praw'], s['vsz'], s['rawsz'], 'FLAT' if s['va']==s['praw'] else '*** NOT FLAT ***'))
print()
print("=== CONTROL 1: DARK negative control ===")
r = 0x5A6AC40
print("  ULokiRespawnComponent::Respawn 0x5A6AC40 page_nonzero = %d/4096  %s" % (
    im.page_nonzero(r), "PASS (dark)" if im.page_nonzero(r)==0 else "*** FAIL ***"))
print()
print("=== CONTROL 2: fold constants byte-exact ===")
folds = {0x0F7EC20:'c20000', 0x0F7EB50:'33c0c3', 0x0F7EB60:'32c0c3', 0x0B9E1F0:'b001c3', 0x0FC6CF0:'0f57c0c3'}
allok=True
for rva, exp in folds.items():
    got = im.read(rva, len(exp)//2).hex()
    ok = got==exp
    allok &= ok
    print("  %#09x expect %-10s got %-10s %s" % (rva, exp, got, "PASS" if ok else "*** FAIL ***"))
print()
print("=== CONTROL 3: LIT positive controls (lane-relevant) ===")
pos = {
 0x55CCCB0:'AuthPlayerDetachPlayerFromRidable (TARGET)',
 0x55D89F0:'GetLandingTeleportLocation',
 0x5599040:'SetPredropHidden',
 0x339A550:'SetActorEnableCollision',
 0x55AC8E0:'GetLokiCharacterMovement',
 0x035EC850:'ENGINE PhysFalling',
 0x055C2430:'ULokiCMC::StartNewPhysics',
}
for rva,name in pos.items():
    n = im.page_nonzero(rva)
    print("  %#09x %-42s page_nonzero=%4d/4096 %s" % (rva, name, n, "LIT" if n>0 else "*** DARK ***"))
