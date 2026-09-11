import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
D=im.data
def scan(tok, wide=False):
    b=tok.encode('utf-16-le' if wide else 'latin1')
    # need NUL-terminated + preceded by NUL to be a standalone string
    out=[]; o=0
    while True:
        o=D.find(b,o)
        if o<0: break
        out.append(o); o+=1
    return out
def rva_of(off):
    for s in im.sections:
        if s['praw']<=off<s['praw']+s['rawsz']: return s['va']+(off-s['praw']), s['name']
    return None,'?'
print("TOKEN                                 ASCII-hits  WIDE-hits   first ASCII rva/sec")
for tok in ['SpawnedAttributes','K2_InitStats','InitStats','GetOrCreateAttributeSubobject',
            'AddSpawnedAttribute','GetAttributeSubobject','AddAttributeSetSubobject',
            'AttributeSetStorage','AbilitySystemComponentStorage','MaxAcceleration',
            'MoveSpeed','MaxMoveSpeed','LokiAttributeSet','KERNEL32']:
    a=scan(tok); w=scan(tok,True)
    r,sec=rva_of(a[0]) if a else (None,'-')
    print(f"  {tok:36s} {len(a):6d}     {len(w):6d}     {(hex(r) if r else '-'):>12s} {sec}")
