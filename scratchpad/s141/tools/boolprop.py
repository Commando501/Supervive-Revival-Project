import sys, struct
sys.path.insert(0,'.')
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase; data=im.data
sec={s['name']:s for s in im.sections}
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); CS.detail=True
def find_name(tok):
    s=sec['.rdata']; buf=data[s['praw']:s['praw']+s['vsz']]
    pat=b'\0'+tok.encode()+b'\0'; res=[]; i=0
    while True:
        j=buf.find(pat,i)
        if j<0: break
        res.append(s['va']+j+1); i=j+1
    return res
def refs(rva):
    out=[]; tgt=(IB+rva).to_bytes(8,'little')
    for sn in ('.rdata','.data'):
        s=sec[sn]; buf=data[s['praw']:s['praw']+s['vsz']]; i=0
        while True:
            j=buf.find(tgt,i)
            if j<0: break
            va=s['va']+j
            if va%8==0: out.append((sn,va))
            i=j+1
    return out
TX=sec['.text']
def decode_bool(rec):
    b=im.read(rec,0x60)
    qs=[struct.unpack_from('<Q',b,k)[0] for k in range(0,0x60,8)]
    # find any qword that is a .text pointer -> candidate SetBitFunc
    cands=[]
    for k,q in enumerate(qs):
        if q>IB:
            r=q-IB
            if TX['va']<=r<TX['va']+TX['vsz']:
                bb=im.read(r,16)
                ins=list(CS.disasm(bb,r))[:3]
                txt='; '.join(f"{i.mnemonic} {i.op_str}" for i in ins)
                cands.append((k*8, r, bb[:8].hex(), txt))
    return cands
for tok in sys.argv[1:]:
    for na in find_name(tok):
        for sn,r in refs(na):
            nb=struct.unpack_from('<Q', im.read(r,8),0)[0]
            if nb-IB!=na: continue
            print(f"### {tok}  rec@{sn} {r:#010x}")
            for off,fr,hx,txt in decode_bool(r):
                print(f"    [+{off:#04x}] .text {fr:#09x}  {hx}  {txt}")
