import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase; D=im.data
def ptrs_to(rva, secname=None):
    t=(rva+IB).to_bytes(8,'little'); out=[]
    for s in im.sections:
        if secname and s['name']!=secname: continue
        o=s['praw']; end=s['praw']+s['rawsz']
        while True:
            o=D.find(t,o)
            if o<0 or o>=end: break
            out.append((s['name'], s['va']+(o-s['praw']))); o+=8
    return out
print("=== pointers to 'K2_InitStats' string 0x839A730")
for sec,r in ptrs_to(0x839A730):
    print(f"   {sec} {r:#x}")
    blob=im.read(r,0x18)
    for i in range(0,0x18,8):
        v=struct.unpack_from('<Q',blob,i)[0]
        print(f"      +{i:#04x} = {v:#018x}  rva={(v-IB):#x}" if v>IB else f"      +{i:#04x} = {v:#018x}")
print()
print("=== 0x4415DF0 (claimed exec thunk)  bytes:", im.read(0x4415DF0,24).hex())
print("=== 0x4481AC0 (claimed InitStats impl) bytes:", im.read(0x4481AC0,24).hex())
print("=== fold-compare: is 0x4481AC0 any fold?",
      im.read(0x4481AC0,4).hex() in ('c2000000','33c0c300','32c0c300','b001c300','0f57c0c3'))
print()
for rva,nm in ((0x52AC650,'ULokiAttributeSet::GetPrivateStaticClass?'),
               (0x52B8200,'ULokiAttributeSetHealth?'),(0x442B550,'UAttributeSet?')):
    print(f"=== {rva:#x} {nm}: {im.read(rva,16).hex()}")
