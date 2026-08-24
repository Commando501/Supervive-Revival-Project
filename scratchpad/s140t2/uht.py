import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s140t2')
from pe import PE

GEN = {0x00:'Byte',0x01:'Int8',0x02:'Int16',0x03:'Int',0x04:'Int64',0x05:'UInt16',0x06:'UInt32',
 0x07:'UInt64',0x08:'UnsizedInt',0x09:'UnsizedUInt',0x0A:'Float',0x0B:'Double',0x0C:'Bool',
 0x0D:'SoftClass',0x0E:'WeakObject',0x0F:'LazyObject',0x10:'SoftObject',0x11:'Class',0x12:'Object',
 0x13:'Interface',0x14:'Name',0x15:'Str',0x16:'Array',0x17:'Map',0x18:'Set',0x19:'Struct',
 0x1A:'Delegate',0x1B:'InlineMulticastDelegate',0x1C:'SparseMulticastDelegate',0x1D:'Text',
 0x1E:'Enum',0x1F:'FieldPath',0x20:'LargeWorldCoordinatesReal',0x21:'Optional'}

def genname(g):
    base = g & 0xFF
    mods=[]
    if g & 0x100: mods.append('NativeBool')
    if g & 0x200: mods.append('ObjectPtr')
    if g & 0x400: mods.append('m400')
    if g & 0x800: mods.append('m800')
    return GEN.get(base,'?%#x'%base)+(('|'+'|'.join(mods)) if mods else '')

def cstr_rvas(p, s):
    pat=s.encode()+b'\0'
    out=[]
    for nm,va,vsz,praw,rawsz in p.sec:
        blob=p.d[praw:praw+rawsz]; i=0
        while True:
            j=blob.find(pat,i)
            if j<0: break
            if j==0 or blob[j-1]==0: out.append(va+j)
            i=j+1
    return out

def rec(p, r):
    b=p.rd(r,0x40)
    name_va,rep_va=struct.unpack_from('<QQ',b,0)
    flags=struct.unpack_from('<Q',b,0x10)[0]
    genf,objf=struct.unpack_from('<II',b,0x18)
    setter,getter=struct.unpack_from('<QQ',b,0x20)
    ad,off=struct.unpack_from('<HH',b,0x30)
    ext=struct.unpack_from('<Q',b,0x38)[0]
    nm=None
    try:
        if name_va>p.base: nm=p.cstr(name_va-p.base,128)
    except Exception: pass
    return dict(rva=r,name=nm,flags=flags,genf=genf,gen=genname(genf),objf=objf,
                setter=setter,getter=getter,arraydim=ad,off=off,ext=ext)

def records_for(p, name):
    out=[]
    for s in cstr_rvas(p,name):
        for a in p.findptr(s, 8):
            d=rec(p,a)
            if d['name']==name: out.append(d)
    return out
