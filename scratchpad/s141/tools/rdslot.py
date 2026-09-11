import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase
FOLDS={0x0F7EC20:'FOLD void ret0',0x0F7EB50:'FOLD null/false',0x0F7EB60:'FOLD false',0x0B9E1F0:'FOLD true',0x0FC6CF0:'FOLD 0.0f'}
vt=int(sys.argv[1],16)
for d in [int(x,16) for x in sys.argv[2:]]:
    v=struct.unpack_from('<Q', im.read(vt+d,8),0)[0]
    r=v-IB if v>IB else None
    tag = FOLDS.get(r,'')
    nz = im.page_nonzero(r) if r else 0
    print(f"  vt {vt:#09x} disp {d:#05x} (slot {d//8}) -> {r:#09x} page {nz}/4096 {tag}")
