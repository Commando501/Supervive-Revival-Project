import sys, struct, json, re
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB = im.imagebase
data = im.data
sec = {s['name']:s for s in im.sections}
TX = sec['.text']; RD = sec['.rdata']; DA = sec['.data']
tlo, thi = TX['va'], TX['va']+TX['vsz']
rlo, rhi = RD['va'], RD['va']+RD['vsz']
NAME = re.compile(rb'^[A-Za-z_][A-Za-z0-9_]{2,79}\0')
out = []
base = DA['praw']; n = DA['vsz']
buf = data[base:base+n]
i = 0
while i + 24 <= n:
    a = struct.unpack_from('<Q', buf, i)[0]
    if a > IB and (a-IB) >= rlo and (a-IB) < rhi:
        b,c = struct.unpack_from('<QQ', buf, i+8)
        if b > IB and c > IB:
            rb, rc = b-IB, c-IB
            if tlo <= rb < thi and tlo <= rc < thi:
                ra = a-IB
                s = data[RD['praw']+(ra-rlo): RD['praw']+(ra-rlo)+80]
                m = NAME.match(s)
                if m:
                    out.append((DA['va']+i, m.group(0)[:-1].decode(), rb, rc))
                    i += 24; continue
    i += 8
print("records:", len(out))
with open('recs.json','w') as f:
    json.dump([[r[0],r[1],r[2],r[3]] for r in out], f)
