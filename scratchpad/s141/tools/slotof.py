import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase
VTS = {'ULokiCMC':0x088F8570, 'EngineCMC':0x07FBED58}
def scan(vt, n=0x1200):
    b = im.read(vt, n)
    out={}
    for k in range(0, n, 8):
        v = struct.unpack_from('<Q', b, k)[0]
        if v>IB and (v-IB)<im.sizeofimage:
            out[k]=v-IB
    return out
tab = {name: scan(vt) for name,vt in VTS.items()}
for t in sys.argv[1:]:
    tr = int(t,16)
    for name,d in tab.items():
        hits=[f"disp {k:#05x} (slot {k//8})" for k,v in d.items() if v==tr]
        print(f"{tr:#09x} in {name}: {hits if hits else 'not found'}")
