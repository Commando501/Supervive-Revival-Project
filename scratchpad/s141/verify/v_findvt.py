import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
rd=[s for s in im.sections if s['name']=='.rdata'][0]
data=im.data[rd['praw']:rd['praw']+rd['rawsz']]
target=(0x55AC9F0+IB).to_bytes(8,'little')
hits=[]
o=0
while True:
    o=data.find(target,o)
    if o<0: break
    hits.append(rd['va']+o); o+=8
print(f"slots holding 0x55AC9F0 in .rdata: {len(hits)}")
for h in hits[:40]:
    print(f"  slot at .rdata {h:#x}  -> implies vtable base {h-0xC00:#x} if disp 0xC00")
