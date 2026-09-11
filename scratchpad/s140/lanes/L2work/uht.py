import sys,io,struct
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); BASE=im.imagebase; d=im.data
def astr(rva,maxn=64):
    try: b=im.read(rva,maxn)
    except Exception: return None
    out=[]
    for x in b:
        if x==0: return ''.join(out) if out else None
        if not (32<=x<127): return None
        out.append(chr(x))
    return None
def find_va_all(rva):
    t=struct.pack('<Q',BASE+rva); out=[]
    for s in im.sections:
        if s['name'] not in ('.rdata','.data','_RDATA'): continue
        st=s['praw']; en=st+s['rawsz']; i=st
        while True:
            j=d.find(t,i,en)
            if j<0: break
            out.append((s['name'], j-s['praw']+s['va'])); i=j+8
    return out
MASKS={0x01:0x0350c240,0x02:0x0350c250,0x04:0x0350c260,0x08:0x0350c270,0x10:0x0350c300,
       0x20:0x0350c310,0x40:0x0350c320,0x80:0x0350c330,0x100:0x0350c340,0x200:0x0350c350,0x400:0x0350c360}
for mask,fn in sorted(MASKS.items()):
    occ=find_va_all(fn)
    names=[]
    for secn,at in occ:
        # scan back up to 0x60 for a qword pointing at an ascii string
        for back in range(8,0x60,8):
            try: v=struct.unpack('<Q',im.read(at-back,8))[0]
            except Exception: continue
            if BASE<=v<BASE+im.sizeofimage:
                s=astr(v-BASE)
                if s and s[0].isalpha():
                    names.append((secn,at,back,s)); break
    print(f"mask {mask:#06x} SetBitFunc {fn:#010x}: occ={len(occ)}")
    for secn,at,back,s in names:
        print(f"      [{secn}] rec-ptr @{at:#010x}  name at -{back:#x} = {s!r}")
