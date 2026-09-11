import struct, sys
PATH = r"G:/git/Supervive Revival Project/dumps/merged12.dump.exe"
_f = open(PATH,'rb')
def rd(off, n):
    _f.seek(off); return _f.read(n)
DATA = None
def load_all():
    global DATA
    if DATA is None:
        _f.seek(0); DATA = _f.read()
    return DATA
# PE header
mz = rd(0,0x40)
e_lfanew = struct.unpack_from('<I', mz, 0x3c)[0]
pe = rd(e_lfanew, 0x200)
assert pe[:4]==b'PE\x00\x00', pe[:4]
nsec = struct.unpack_from('<H', pe, 6)[0]
optsz = struct.unpack_from('<H', pe, 0x14)[0]
magic = struct.unpack_from('<H', pe, 0x18)[0]
IMAGEBASE = struct.unpack_from('<Q', pe, 0x18+0x18)[0]
secoff = e_lfanew + 0x18 + optsz
SECS=[]
for i in range(nsec):
    s = rd(secoff+i*40, 40)
    name = s[:8].rstrip(b'\x00').decode()
    vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', s, 8)
    SECS.append((name, va, vsz, rawptr, rawsz))
def sec_of(rva):
    for n,va,vsz,rp,rs in SECS:
        if va <= rva < va+max(vsz,rs): return n
    return None
def page_nonzero(rva):
    base = rva & ~0xFFF
    b = rd(base, 0x1000)
    return sum(1 for x in b if x)
def u64(rva): return struct.unpack_from('<Q', rd(rva,8),0)[0]
def u32(rva): return struct.unpack_from('<I', rd(rva,4),0)[0]
def hx(rva,n): return rd(rva,n).hex()
FOLDS = {0x00F7EC20:'FOLD.void(c20003)',0x00F7EB50:'FOLD.null(33c0c3)',0x00F7EB60:'FOLD.false(32c0c3)',0x00B9E1F0:'FOLD.true(b001c3)',0x00FC6CF0:'FOLD.zerof'}
def grade(rva):
    if rva in FOLDS: return FOLDS[rva]
    nz = page_nonzero(rva)
    if nz==0: return 'DARK(0/4096)'
    return 'REAL(pg %d/4096)'%nz
if __name__=='__main__':
    print('ImageBase 0x%X  nsec=%d'%(IMAGEBASE,nsec))
    for s in SECS: print('  %-8s va=0x%08X vsz=0x%08X rawptr=0x%08X rawsz=0x%08X  rawptr==va? %s'%(s[0],s[1],s[2],s[3],s[4], s[3]==s[1]))
