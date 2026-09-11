import sys
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); data=im.data
for tok in sys.argv[1:]:
    w=tok.encode('utf-16-le')
    for s in im.sections:
        buf=data[s['praw']:s['praw']+s['rawsz']]; i=0
        while True:
            j=buf.find(w,i)
            if j<0: break
            va=s['va']+j
            # back up to start of the wide string
            k=j
            while k>=2 and buf[k-2:k]!=b'\0\0': k-=2
            txt=buf[k:k+400]
            e=txt.find(b'\0\0')
            print(f"  {s['name']} {s['va']+k:#010x}: {txt[:e if e>=0 else 200].decode('utf-16-le','replace')!r}")
            i=j+1
