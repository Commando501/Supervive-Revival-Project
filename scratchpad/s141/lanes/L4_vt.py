import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
BASE = im.imagebase
FOLDS = {0x0F7EC20:'VOIDret0',0x0F7EB50:'nullptr/false',0x0F7EB60:'false',0x0B9E1F0:'true',0x0FC6CF0:'0.0f'}
def rd_slot(vt_rva, disp):
    va = struct.unpack_from('<Q', im.read(vt_rva+disp, 8))[0]
    return va - BASE if va else 0
def grade(rva):
    if rva==0: return "NULL",""
    pn = im.page_nonzero(rva)
    if pn==0: return "DARK",""
    for f,n in FOLDS.items():
        L=4 if f==0x0FC6CF0 else 3
        if im.read(rva,L)==im.read(f,L): return "FOLD", "%#x %s"%(f,n)
    ins=list(md.disasm(im.read(rva,32), rva))
    return "REAL", "; ".join("%s %s"%(i.mnemonic,i.op_str) for i in ins[:6])

LOKI_VT = 0x088F8570
ENG_VT  = 0x07FBED58
print("=== ULokiCMC vtable %#x vs ENGINE UCharacterMovementComponent vtable %#x ===" % (LOKI_VT, ENG_VT))
print("(.rdata holds ABSOLUTE VAs; ImageBase %#x subtracted)" % BASE)
print()
print("--- neighbourhood of disp 0x3E0 (slot %d) ---" % (0x3E0//8))
for disp in range(0x3A0, 0x430, 8):
    l = rd_slot(LOKI_VT, disp); e = rd_slot(ENG_VT, disp)
    gl,tl = grade(l)
    mark = "  <=== THE CALL" if disp==0x3E0 else ("  (loki override)" if l!=e else "")
    print("  disp %#05x slot %3d  loki=%#09x  eng=%#09x  %-6s %s%s" % (disp, disp//8, l, e, gl, "SAME" if l==e else "DIFF", mark))
print()
print("--- disp 0x3E0 full grade ---")
for nm,vt in (("ULokiCMC",LOKI_VT),("ENGINE CMC",ENG_VT)):
    r = rd_slot(vt,0x3E0); g,t = grade(r)
    print("  %-12s -> %#09x  %s  %s" % (nm, r, g, t[:140]))
