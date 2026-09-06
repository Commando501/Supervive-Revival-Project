import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
IB=im.imagebase; VT=0x088F8570
FOLDS={0x00F7EC20:'ret0-void',0x00F7EB50:'null',0x00F7EB60:'false',0x00B9E1F0:'true',0x00FC6CF0:'0.0f'}
def slot(disp): return struct.unpack_from('<Q', im.buf, VT+disp)[0]-IB

def grade_and_rets(t, cap=60000):
    if t in FOLDS: return FOLDS[t], 0, 0
    if im.page_nonzero(t)==0: return 'DARK', 0, 0
    c=CFG2(im,t)
    return 'REAL', len(c.ins), len(c.rets)

print("=== the 7 in-R indirect sites L1 did NOT resolve (base = [rbx] = this -> ULokiCMC vtable) ===")
for site,disp in [(0x035EA154,0x8a0),(0x035EA249,0xb68),(0x035EA255,0x6b8),
                  (0x035EA41F,0xc88),(0x035EA44C,0xc90),(0x035EA468,0x608),(0x035EB086,0x608)]:
    t=slot(disp)
    g,n,r=grade_and_rets(t)
    print(f"  {site:#010x} disp {disp:#05x} -> {t:#010x}  nz={im.page_nonzero(t):4d}  {g:5}  insns={n:5d} rets={r}")

print("\n=== the two [rcx+0x878] sites: rcx provenance ===")
for site in (0x035EA26D, 0x035EA317):
    lo=site-0x40
    for i in md.disasm(im.read(lo,0x40+8), lo):
        if i.address> site: break
        if i.address>=site-0x30:
            print(f"   {i.address:#010x} {im.read(i.address,i.size).hex():<20} {i.mnemonic} {i.op_str}")
    print("   ---")
