import struct,re,capstone,sys
d=open('dumps/merged12.dump.exe','rb').read()
IB=0x7ff6af000000
TEXT=(0x1000,0x1000+0x7649000)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)

def cstr(rva,m=160):
    if rva<0 or rva>=len(d): return None
    e=d.find(b'\x00',rva,rva+m)
    if e<0: return None
    try:
        s=d[rva:e].decode('ascii')
    except: return None
    return s if s and all(32<=ord(c)<127 for c in s) else None
def wstr(rva,m=200):
    if rva<0 or rva>=len(d): return None
    b=d[rva:rva+m]; e=b.find(b'\x00\x00')
    if e<0: return None
    if e%2: e+=1
    try:
        s=b[:e].decode('utf-16-le')
    except: return None
    return s if s and all(32<=ord(c)<127 for c in s) else None
def q(rva): return struct.unpack_from('<Q',d,rva)[0]
def findall(pat,limit=200):
    out=[];i=d.find(pat)
    while i>=0 and len(out)<limit:
        out.append(i);i=d.find(pat,i+1)
    return out
def findptr(rva,limit=50): return findall(struct.pack('<Q',IB+rva),limit)

# --- classify a record base (name ptr at +0x00, typefunc at +0x38) ---
def recname(rb):
    if rb<0 or rb+0x40>len(d): return None
    p=q(rb)
    if not (IB<=p<IB+len(d)): return None
    return cstr(p-IB)

def classname_from_ctor(fn):
    b=d[fn:fn+0x200]
    for i in md.disasm(b,fn):
        m=re.search(r'rip \+ (0x[0-9a-f]+)|rip - (0x[0-9a-f]+)',i.op_str)
        if m and i.mnemonic=='lea':
            off=int(m.group(1),16) if m.group(1) else -int(m.group(2),16)
            t=i.address+i.size+off
            s=wstr(t)
            if s and not s.startswith('/'): return s,t
        if i.mnemonic=='ret': break
    return None,None

def owner_of_record(rb):
    """record base -> (classname, classparams_rva, proparray_rva, nprops)"""
    slots=findptr(rb,20)
    for s in slots:
        # walk back to array start
        st=s
        while st-8>=0:
            v=q(st-8)
            if IB<=v<IB+len(d) and recname(v-IB): st-=8
            else: break
        cps=findptr(st,20)
        for cp in cps:
            base=cp-0x28
            fn=q(base)
            if IB<=fn<IB+len(d):
                f=fn-IB
                if TEXT[0]<=f<TEXT[1]:
                    nm,_=classname_from_ctor(f)
                    if nm:
                        cnt=struct.unpack_from('<I',d,base+0x38)[0]
                        return nm,base,st,(cnt>>15)&0x7FF
    return None,None,None,None
