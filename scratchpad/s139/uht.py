#!/usr/bin/env python3
"""Enumerate a UCLASS's UHT FPropertyParams array -> name/type/offset, from .rdata."""
import os, struct, sys
IMG = sys.argv[1] if len(sys.argv)>1 and sys.argv[1].endswith('.exe') else r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
GEN = {0x00:'Byte',0x01:'Int8',0x02:'Int16',0x03:'Int',0x04:'Int64',0x05:'UInt16',0x06:'UInt32',
 0x07:'UInt64',0x0A:'Float',0x0B:'Double',0x0C:'Bool',0x0D:'SoftClass',0x0E:'WeakObject',
 0x0F:'LazyObject',0x10:'SoftObject',0x11:'Class',0x12:'Object',0x13:'Interface',0x14:'Name',
 0x15:'Str',0x16:'Array',0x17:'Map',0x18:'Set',0x19:'Struct',0x1A:'Delegate',
 0x1B:'InlineMulticastDelegate',0x1C:'SparseMulticastDelegate',0x1D:'Text',0x1E:'Enum',
 0x1F:'FieldPath',0x20:'LWCReal',0x21:'Optional',0x22:'VValue'}
class Img:
    def __init__(s,p):
        s.d=open(p,'rb').read(); d=s.d
        e=struct.unpack_from('<I',d,0x3C)[0]
        nsec=struct.unpack_from('<H',d,e+6)[0]; szopt=struct.unpack_from('<H',d,e+20)[0]
        s.imagebase=struct.unpack_from('<Q',d,e+24+24)[0]
        s.sections=[]
        for i in range(nsec):
            o=e+24+szopt+i*40
            nm=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rsz,rp=struct.unpack_from('<IIII',d,o+8)
            s.sections.append((nm,va,vsz))
        s.size=max(va+vs for _,va,vs in s.sections)
    def sec(s,rva):
        for nm,va,vs in s.sections:
            if va<=rva<va+vs: return nm
        return None
    def q(s,rva): return struct.unpack_from('<Q',s.d,rva)[0]
    def rva(s,ptr):
        r=ptr-s.imagebase
        return r if 0<r<s.size else None
    def cstr(s,rva,n=128):
        b=s.d[rva:rva+n]; i=b.find(b'\0'); return b[:i if i>=0 else n].decode('latin1')
im=Img(IMG)

def find_ascii(name):
    pat=b'\x00'+name.encode()+b'\x00'; out=[]
    for nm,va,vs in im.sections:
        if nm not in ('.rdata','.data'): continue
        b=im.d[va:va+vs]; p=0
        while True:
            i=b.find(pat,p)
            if i<0: break
            out.append(va+i+1); p=i+1
    return out

def find_qword_refs(target_rva, secs=('.rdata','.data')):
    needle=struct.pack('<Q',im.imagebase+target_rva); out=[]
    for nm,va,vs in im.sections:
        if nm not in secs: continue
        b=im.d[va:va+vs]; p=0
        while True:
            i=b.find(needle,p)
            if i<0: break
            if (va+i)%8==0: out.append(va+i)
            p=i+1
    return out

def decode_prop(rec):
    if rec+0x40>len(im.d): return None
    npt=im.q(rec); nr=im.rva(npt)
    if nr is None or im.sec(nr) not in ('.rdata','.data'): return None
    name=im.cstr(nr)
    if not name or not all(c.isalnum() or c=='_' for c in name): return None
    rep=im.q(rec+8)
    if rep and im.rva(rep) is None: return None
    pflags=im.q(rec+0x10)
    gen=struct.unpack_from('<I',im.d,rec+0x18)[0]
    ofl=struct.unpack_from('<I',im.d,rec+0x1C)[0]
    adim,off=struct.unpack_from('<HH',im.d,rec+0x30)
    if gen>>8: return None
    if (gen&0x3F) not in GEN: return None
    if adim==0 or adim>64: return None
    ty=GEN[gen&0x3F]+('/ObjPtr' if gen&0x40 else '')
    extra=''
    if (gen&0x3F)==0x0C:  # bool: decode SetBitFunc
        sbf=im.q(rec+0x20); r=im.rva(sbf)
        if r:
            b=im.d[r:r+16]
            extra=' setbit@0x%X:%s'%(r,b[:9].hex())
    return dict(rec=rec,name=name,off=off,ty=ty,gen=gen,pflags=pflags,objflags=ofl,dim=adim,extra=extra)

def walk_array(anchor_ptr_slot):
    """given an rdata slot holding a ptr to a prop record, expand contiguous run"""
    lo=anchor_ptr_slot
    while lo-8>=0:
        p=im.q(lo-8); r=im.rva(p)
        if r is None or decode_prop(r) is None: break
        lo-=8
    hi=anchor_ptr_slot
    while True:
        p=im.q(hi+8); r=im.rva(p)
        if r is None or decode_prop(r) is None: break
        hi+=8
    return lo,hi

if __name__=='__main__':
    anchor=sys.argv[-1]
    strs=find_ascii(anchor)
    print("anchor '%s': %d ascii literal(s) at %s"%(anchor,len(strs),[hex(x) for x in strs]))
    seen=set()
    for s in strs:
        for pr in find_qword_refs(s):
            d=decode_prop(pr)
            if not d: continue
            for slot in find_qword_refs(pr):
                lo,hi=walk_array(slot)
                n=(hi-lo)//8+1
                key=(lo,hi)
                if key in seen or n<3: continue
                seen.add(key)
                print("\n=== PropPointers array 0x%08X..0x%08X  (%d entries)"%(lo,hi,n))
                for k in range(n):
                    rr=im.rva(im.q(lo+k*8)); dd=decode_prop(rr)
                    print("  [%3d] %-46s off=0x%04X (%5d) %-18s dim=%d pflags=0x%016X%s"%(
                        k,dd['name'],dd['off'],dd['off'],dd['ty'],dd['dim'],dd['pflags'],dd['extra']))
