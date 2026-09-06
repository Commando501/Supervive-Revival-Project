import sys, struct, os
BASE = 0x7FF6AF000000
DUMPS = {
 'merged4': r'G:\git\Supervive Revival Project\dumps\merged4.dump.exe',
 'merged3': r'G:\git\Supervive Revival Project\dumps\merged3.dump.exe',
 'merged2': r'G:\git\Supervive Revival Project\dumps\merged2.dump.exe',
 'merged':  r'G:\git\Supervive Revival Project\dumps\merged.dump.exe',
}
_cache={}
def img(name='merged4'):
    if name not in _cache:
        with open(DUMPS[name],'rb') as f: _cache[name]=f.read()
    return _cache[name]

def rva(x):
    """accept VA or RVA"""
    if x >= BASE: return x-BASE
    return x

def rd(a, n, dump='merged4'):
    a=rva(a); return img(dump)[a:a+n]
def u8(a,d='merged4'):  return rd(a,1,d)[0]
def u16(a,d='merged4'): return struct.unpack('<H', rd(a,2,d))[0]
def u32(a,d='merged4'): return struct.unpack('<I', rd(a,4,d))[0]
def u64(a,d='merged4'): return struct.unpack('<Q', rd(a,8,d))[0]
def ptr(a,d='merged4'):
    v=u64(a,d)
    return v
def cstr(a,d='merged4',maxn=200):
    a=rva(a); b=img(d); e=b.find(b'\x00',a,a+maxn); return b[a:e].decode('utf8','replace')
def wstr(a,d='merged4',maxn=400):
    a=rva(a); b=img(d)
    out=[]
    for i in range(0,maxn,2):
        c=b[a+i]|(b[a+i+1]<<8)
        if c==0: break
        out.append(chr(c))
    return ''.join(out)
def hexd(a,n,d='merged4'):
    a=rva(a); b=img(d)
    out=[]
    for i in range(0,n,16):
        chunk=b[a+i:a+i+16]
        out.append('%08X: %s' % (a+i, ' '.join('%02x'%c for c in chunk)))
    return '\n'.join(out)
def iszero(a,n,d='merged4'):
    return all(c==0 for c in rd(a,n,d))
def pagecov(a,n=1,d='merged4'):
    """return list of (page_rva, allzero?)"""
    a=rva(a); res=[]
    p0=a & ~0xFFF; p1=(a+n-1)&~0xFFF
    for p in range(p0,p1+1,0x1000):
        res.append((p, iszero(p,0x1000,d)))
    return res
def dis(a,n=64,d='merged4'):
    import capstone
    md=capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail=True
    a=rva(a)
    out=[]
    for i in md.disasm(rd(a,n,d), a):
        out.append('%08X  %-24s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
    return '\n'.join(out)
