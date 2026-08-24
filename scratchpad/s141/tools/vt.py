import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase; data=im.data
sec={s['name']:s for s in im.sections}
RD=sec['.rdata']; TX=sec['.text']
tlo,thi = TX['va'], TX['va']+TX['vsz']
def slot(vt, disp):
    v = struct.unpack_from('<Q', im.read(vt+disp, 8), 0)[0]
    return v-IB if v>IB else None
# find vtables containing SpawnDefaultController 0x3BBF3C0 at disp 0x8C0
target = (IB+0x3BBF3C0).to_bytes(8,'little')
buf = data[RD['praw']:RD['praw']+RD['vsz']]
hits=[]; i=0
while True:
    j=buf.find(target,i)
    if j<0: break
    va=RD['va']+j
    if va%8==0: hits.append(va)
    i=j+1
print("slots holding APawn::SpawnDefaultController:", len(hits))
cands=[h-0x8C0 for h in hits]
print("=> implied vtable bases (disp 0x8C0):", [hex(c) for c in cands][:40])
