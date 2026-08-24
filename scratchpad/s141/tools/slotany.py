import sys, struct
sys.path.insert(0,'.')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"); IB=im.imagebase
data=im.data; sec={s['name']:s for s in im.sections}
for t in sys.argv[1:]:
    tr=int(t,16); tgt=(IB+tr).to_bytes(8,'little')
    print(f"=== {tr:#x}")
    for sn in ('.rdata',):
        s=sec[sn]; b=data[s['praw']:s['praw']+s['vsz']]; i=0
        while True:
            j=b.find(tgt,i)
            if j<0: break
            va=s['va']+j
            if va%8==0: print(f"   ptr@ {va:#010x}")
            i=j+1
