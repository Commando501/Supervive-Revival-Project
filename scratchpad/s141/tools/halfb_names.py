import sys, json, re, struct
sys.path.insert(0,'.')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"); IB=im.imagebase
FOLD={0x0F7EC20:'FOLD(void ret0)',0x0F7EB50:'FOLD(null/false)',0x0F7EB60:'FOLD(false)',
      0x0B9E1F0:'FOLD(true)',0x0FC6CF0:'FOLD(0.0f)'}
KW=['Knockback','Launch','Impulse','Push','Pull','Dash','Blink','Displace','Teleport',
    'Velocity','Fling','Yeet','Boop','Force']
pat=re.compile('|'.join(KW), re.I)
recs=json.load(open('recs.json'))
def grade(impl):
    if impl in FOLD: return FOLD[impl]
    if im.page_nonzero(impl)==0: return 'DARK'
    b=im.read(impl,4)
    return 'REAL'
hits=[]
for va,name,thunk,impl in recs:
    if pat.search(name):
        hits.append((name,va,thunk,impl,grade(impl)))
hits.sort()
print(f"[.data record table] {len(recs)} records total; matching keyword set: {len(hits)}")
from collections import Counter
print("grades:", Counter(h[4] for h in hits))
json.dump(hits, open('halfb_hits.json','w'))
for n,va,t,i,g in hits:
    print(f"  {n:52s} rec={va:#x} thunk={t:#09x} impl={i:#09x}  {g}")
