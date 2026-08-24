import sys
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); data=im.data
for tok in sys.argv[1:]:
    a = tok.encode(); w = tok.encode('utf-16-le')
    print(f"=== '{tok}'")
    for s in im.sections:
        buf = data[s['praw']:s['praw']+s['rawsz']]
        ca = buf.count(a); cw = buf.count(w)
        if ca or cw:
            locs=[]; i=0
            while len(locs)<6:
                j=buf.find(a,i)
                if j<0: break
                locs.append(hex(s['va']+j)); i=j+1
            print(f"   {s['name']:9s} ascii={ca} wide={cw}  first={locs}")
