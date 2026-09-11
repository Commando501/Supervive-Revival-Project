import struct,sys
from v import im
IB=im.imagebase
def slot(vt,disp):
    q=struct.unpack_from('<Q',im.read(vt+disp,8),0)[0]
    return (q-IB) if q else 0
LOKI=0x088F8570; ENG=0x07FBED58
print("vtable ULokiCMC %#x  engine CMC %#x"%(LOKI,ENG))
for disp in (0x670,0x678,0x6B8,0x720,0x730,0x748,0x750,0x7A0,0x7B0,0x7D0,0x830,0x928,0x970,0x978,0x980,0x988,0x990,0xA50,0xC00,0xCC8,0xCE0,0x4C0,0x4C8,0x4D8,0x3B8):
    l=slot(LOKI,disp); e=slot(ENG,disp)
    print("  disp %#05x  loki %#09x  eng %#09x  %s"%(disp,l,e,"SAME" if l==e else "LOKI-OVERRIDE"))
