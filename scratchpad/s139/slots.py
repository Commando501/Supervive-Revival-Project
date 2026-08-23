import struct,sys
IMG=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
d=open(IMG,'rb').read()
pe=struct.unpack_from('<I',d,0x3c)[0]; IB=struct.unpack_from('<Q',d,pe+24+24)[0]
def slot(vt,disp):
    q=struct.unpack_from('<Q',d,vt+disp)[0]
    return q-IB if q else 0
CMC=0x07FBED58; LOKICMC=0x088F8570
for disp in (0x4C0,0x4E0,0x640,0x6B8,0x810,0x890,0x8A8,0xA98,0xAB8,0xAD0,0xB00,0xB10,0x6F0,0x708,0xAF0,0x3D0):
    print("disp 0x%03X slot %3d  CMC=0x%08X  LokiCMC=0x%08X"%(disp,disp//8,slot(CMC,disp),slot(LOKICMC,disp)))
