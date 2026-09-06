import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase; D=im.data
rd=[s for s in im.sections if s['name']=='.rdata'][0]
def rva_of(off):
    for s in im.sections:
        if s['praw']<=off<s['praw']+s['rawsz']: return s['va']+(off-s['praw'])
    return None
def find_strs(tok):
    b=b'\x00'+tok.encode()+b'\x00'; out=[]; o=0
    while True:
        o=D.find(b,o)
        if o<0: break
        out.append(rva_of(o+1)); o+=1
    return out
def ptrs_to(rva):
    t=(rva+IB).to_bytes(8,'little'); out=[]; o=rd['praw']
    end=rd['praw']+rd['rawsz']
    while True:
        o=D.find(t,o)
        if o<0 or o>=end: break
        out.append(rd['va']+(o-rd['praw'])); o+=8
    return out
for tok in ('MoveSpeed','MaxMoveSpeed','MaxAcceleration','GroundFriction','Mass','BrakingDecelerationWalking'):
    print(f"=== '{tok}' NUL-delimited ASCII strings:")
    for s in find_strs(tok):
        p=ptrs_to(s)
        print(f"   str@{s:#x}  ptrs_in_rdata={[hex(x) for x in p]}")
        for rec in p:
            # UHT FPropertyParamsBase: NameUTF8(8) RepNotify(8) PropertyFlags(8) ObjFlags(4) ArrayDim(4) ... then per-type
            blob=im.read(rec, 0x50)
            print(f"      rec {rec:#x}: "+' '.join(f'{b:02x}' for b in blob[:0x50]))
