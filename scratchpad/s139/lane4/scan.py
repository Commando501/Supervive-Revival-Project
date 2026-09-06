import sys, struct, bisect
sys.path.insert(0,'scratchpad/s139/lane4')
from l4 import *
TEXT_LO,TEXT_HI=0x1000,0x1000+0x7649000
def rel32_callers(target):
    """all E8 rel32 call sites whose target == target"""
    res=[]
    d=DATA
    i=TEXT_LO
    # brute force: scan for E8
    import re
    for m in re.finditer(b'\xe8', d[TEXT_LO:TEXT_HI]):
        p=TEXT_LO+m.start()
        if p+5>TEXT_HI: continue
        rel=struct.unpack_from('<i',d,p+1)[0]
        if p+5+rel==target: res.append(p)
    return res
def rel32_jmp(target):
    res=[]
    import re
    d=DATA
    for m in re.finditer(b'\xe9', d[TEXT_LO:TEXT_HI]):
        p=TEXT_LO+m.start()
        rel=struct.unpack_from('<i',d,p+1)[0]
        if p+5+rel==target: res.append(p)
    return res
def vcall_sites(disp):
    """find `call qword ptr [reg+disp]` FF /2 with disp32 or disp8"""
    res=[]
    import re
    d=DATA
    # FF 90 disp32 (call [rax+d32]) ; modrm reg field=2 -> 0x90..0x97 for disp32, 0x50..0x57 disp8
    pat=struct.pack('<i',disp)
    for m in re.finditer(re.escape(pat), d[TEXT_LO:TEXT_HI]):
        p=TEXT_LO+m.start()
        # check preceding bytes for FF /2 disp32 form
        for back in (2,3):
            s=p-back
            if s<TEXT_LO: continue
            if d[s]==0xFF and 0x90<=d[s+1]<=0x97 and back==2:
                res.append(s)
            if d[s]==0x41 and d[s+1]==0xFF and 0x90<=d[s+2]<=0x97 and back==3:
                res.append(s)
    return sorted(set(res))

def chain_start(rva):
    s,e=pdata(); i=bisect.bisect_right(s,rva)-1
    if i<0: return None
    j=i
    while j>0 and e[j-1]==s[j]: j-=1
    return s[j]
def chain_end(rva):
    s,e=pdata(); i=bisect.bisect_right(s,rva)-1
    j=i
    while j+1<len(s) and e[j]==s[j+1]: j+=1
    return e[j]
BASE_V=0x07FBED58; LOKI_V=0x088F8570
def slots():
    b={}; l={}
    for i in range(413):
        b.setdefault(q(BASE_V+8*i)-IB,[]).append(i)
        l.setdefault(q(LOKI_V+8*i)-IB,[]).append(i)
    return b,l
BSLOT,LSLOT=slots()
def naming(rva):
    cs=chain_start(rva)
    tags=[]
    if cs in BSLOT: tags.append('CMCbase slot '+str(BSLOT[cs]))
    if cs in LSLOT: tags.append('LokiCMC slot '+str(LSLOT[cs]))
    return cs,tags
