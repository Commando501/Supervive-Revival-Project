import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
FOLD={0x0F7EC20:'FOLD void',0x0F7EB50:'FOLD null/false',0x0F7EB60:'FOLD false',0x0B9E1F0:'FOLD true',0x0FC6CF0:'FOLD 0.0f'}
def ent(vt,disp):
    va=struct.unpack('<Q', im.read(vt+disp,8))[0]
    return va-IB if va>IB else va
LOKI=0x088F8570; ENG=0x07FBED58
print(f"ImageBase {IB:#x}   (.rdata holds ABSOLUTE VAs -- subtracting ImageBase)")
print(f"{'disp':>7} {'name':<28} {'ULokiCMC vt 0x88F8570':<26} {'engine vt 0x7FBED58':<26} grade(Loki)")
for disp,name in [(0x4C0,'GetGravityZ'),(0x4C8,'GetMaxSpeed'),(0x7A0,'NewFallVelocity'),
                  (0x7B0,'CalcVelocity'),(0x7D0,'GetMaxAcceleration'),(0x830,'PhysFalling'),
                  (0x660,'ComputeAnalogInputModifier'),(0xA50,'clears +0x16C8'),(0x7D8,'?'),
                  (0x838,'? (called at 0x35EC8BB)'),(0x840,'? (called at 0x35EC91B)'),
                  (0xC80,'? (0x35ECD0F)')]:
    a=ent(LOKI,disp); b=ent(ENG,disp)
    try: nz=im.page_nonzero(a); f8=im.read(a,8).hex()
    except Exception: nz=-1; f8='??'
    g='FOLD' if a in FOLD else ('DARK' if nz==0 else 'REAL')
    ov='LOKI-OVERRIDE' if a!=b else 'not overridden'
    print(f"{disp:#7x} {name:<28} {a:#010x} {'':<14} {b:#010x} {'':<14} {g}  {ov}  page={nz}")
