import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB = im.imagebase
def rva(va): return va-IB if va>=IB else None
for probe in (0x09BC9AD0, 0x9C1F328, 0x9C1F298):
    b = im.read(probe, 24)
    a,bb,c = struct.unpack('<QQQ', b)
    print(f"{probe:#x}: {a:#x} {bb:#x} {c:#x}")
    for v,lbl in ((a,'name'),(bb,'thunk'),(c,'impl')):
        r = rva(v)
        if r is None: print(f"   {lbl}: not a VA"); continue
        s = im.sec_of(r)
        extra=''
        if s and s['name']=='.rdata':
            raw = im.read(r, 64); nul = raw.find(b'\0')
            extra = ' STR=' + repr(raw[:nul if nul>=0 else 64])
        print(f"   {lbl}: rva {r:#x} sec {s['name'] if s else '?'}{extra}")
