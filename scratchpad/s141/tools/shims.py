import sys, struct, json
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG)
sec={s['name']:s for s in im.sections}; TX=sec['.text']
buf = im.data[TX['praw']:TX['praw']+TX['vsz']]
# mov rax,[rcx] ; jmp [rax+disp32]  = 48 8b 01 ff a0 dd dd dd dd
pat = bytes.fromhex('488b01ffa0')
shim={}; i=0
while True:
    j=buf.find(pat,i)
    if j<0: break
    disp=struct.unpack_from('<I', buf, j+5)[0]
    shim[TX['va']+j]=disp
    i=j+1
# also the 8-bit form: 48 8b 01 ff 60 dd
pat2 = bytes.fromhex('488b01ff60'); i=0
while True:
    j=buf.find(pat2,i)
    if j<0: break
    shim[TX['va']+j]=buf[j+5]
    i=j+1
print("dispatch shims found:", len(shim))
json.dump({hex(k):v for k,v in shim.items()}, open('shims.json','w'))
recs=json.load(open('recs.json'))
terms=[t.lower() for t in sys.argv[1:]]
for rec_va,name,thunk,impl in recs:
    if impl in shim and (not terms or any(t in name.lower() for t in terms)):
        print(f"  {name:42s} impl {impl:#09x} -> VTABLE DISP {shim[impl]:#06x} (slot {shim[impl]//8})")
