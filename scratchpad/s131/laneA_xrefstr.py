import sys, struct, collections
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img=fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
IB=img.imagebase; b=img.buf
tsec=[s for s in img.sections if s[0]=='.text'][0]
def wstr(r,maxn=300):
    o=[];j=r
    while True:
        c=b[j]|(b[j+1]<<8)
        if c==0 or len(o)>maxn: break
        o.append(chr(c)); j+=2
    return "".join(o)
def astr(r,maxn=200):
    o=[]
    for c in b[r:r+maxn]:
        if c==0: break
        if c<32 or c>126: return None
        o.append(chr(c))
    return "".join(o)
def ptr_slots(rva):
    pat=struct.pack("<Q", IB+rva); out=[]
    for name,va,vs,rp,rs in img.sections:
        if name in ('.reloc','.rsrc'): continue
        blob=b[rp:rp+rs]; st=0
        while True:
            i=blob.find(pat,st)
            if i<0: break
            out.append((name,va+i)); st=i+1
    return out
def riprefs(rva, limit=50):
    """disp32 windows in .text resolving to rva"""
    nm,va,vs,rp,rs=tsec
    blob=b[rp:rp+rs]; out=[]
    for i in range(0,len(blob)-4):
        d=struct.unpack_from("<i",blob,i)[0]
        if d and va+i+4+d==rva:
            out.append(va+i)
            if len(out)>=limit: break
    return out
for s in (0x08B20D40,0x08B20490,0x08B20590,0x08B33CC0):
    print(f'=== W"{wstr(s)[:120]}"  @0x{s:08X}')
    for name,slot in ptr_slots(s):
        print(f"   ptr slot {name} 0x{slot:08X}")
        if name=='.rdata':
            rec=slot  # msg ptr is record+0
            f=struct.unpack_from("<Q",b,rec+8)[0]
            ln=struct.unpack_from("<I",b,rec+0x10)[0]
            vb=struct.unpack_from("<I",b,rec+0x14)[0]
            fn=astr(f-IB) if IB<=f<IB+len(b) else None
            print(f"      record: file={fn} line={ln} verbosity={vb}")
            for site in riprefs(rec):
                print(f"      lea-site .text 0x{site-3:07X}..0x{site:07X} (disp32 at 0x{site:07X})")
    print()
