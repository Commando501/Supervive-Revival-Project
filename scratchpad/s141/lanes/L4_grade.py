import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import capstone
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail=True
FOLDS = {0x0F7EC20:'VOID ret0 (c20000)', 0x0F7EB50:'nullptr/false (33c0c3)',
         0x0F7EB60:'false (32c0c3)', 0x0B9E1F0:'true (b001c3)', 0x0FC6CF0:'0.0f (0f57c0c3)'}
def grade(rva):
    pn = im.page_nonzero(rva)
    if pn == 0: return "DARK(0/4096)", ""
    b = im.read(rva, 16)
    for f,name in FOLDS.items():
        fb = im.read(f, 4)
        if b[:len(fb)] == fb and rva!=f: pass
    if rva in FOLDS: return "FOLD", FOLDS[rva]
    # check byte-equality with fold constants
    for f,name in FOLDS.items():
        L = {0x0F7EC20:3,0x0F7EB50:3,0x0F7EB60:3,0x0B9E1F0:3,0x0FC6CF0:4}[f]
        if b[:L] == im.read(f,L): return "FOLD", "== %#x %s" % (f,name)
    ins = list(md.disasm(b, rva))
    txt = "; ".join("%s %s"%(i.mnemonic,i.op_str) for i in ins[:4])
    return "REAL(pg %d)"%pn, txt
callees = [0x56be0d0,0x54f8dc0,0xf7ec20,0x1138dd0,0x10ff910,0x339a550,0x5599040,
           0x5586530,0x55ac8e0,0x55d89f0,0x339a7a0,0x54537c0,0x55c6e80,0x11f3860]
print("=== CALLEE GRADING (14 direct call targets, 13 distinct + 0xf7ec20 twice) ===")
for c in callees:
    g,t = grade(c)
    print("  %#09x  %-14s %s" % (c, g, t[:100]))
