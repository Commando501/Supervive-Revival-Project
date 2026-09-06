# image_diff_namepages.py -- name the code that ran between two dumpimage snapshots.  (S120)
#
# Companion to image_diff_callers.py. Walks the LIVE GUObjectArray for UFunction objects and
# reports any whose native Func (+0xE0) lands in a newly-decrypted page -- the NAMED entry points
# of the flow just driven.
#
# A ZERO HERE IS ITSELF A RESULT: on the hero-mastery claim, 0 of 35,148 live UFunctions landed in
# any new page, independently establishing the flow is pure native C++ rather than a reflected /
# Blueprint entry point -- agreeing with a 69,178-asset census done a completely different way.
#
# Name the code that ran between two dumpimage snapshots.
#
# The pages that are ZERO in BEFORE and non-zero in AFTER were demand-decrypted by the activity
# between the snapshots (decryption is monotone within a process lifetime). This walks the LIVE
# GUObjectArray for UFunction objects and reports any whose native Func (+0xE0) lands in those
# pages -- i.e. the named entry points of the flow we just drove.
#
#   usage: namepages.py <before.dump.exe> <after.dump.exe> <PID> <BASE-hex>
import ctypes, struct, sys
from ctypes import wintypes

before = open(sys.argv[1], 'rb').read()
after = open(sys.argv[2], 'rb').read()
PID = int(sys.argv[3], 0)
BASE = int(sys.argv[4], 16)

pe = struct.unpack_from('<I', after, 0x3C)[0]
nsec = struct.unpack_from('<H', after, pe + 6)[0]
opt = struct.unpack_from('<H', after, pe + 20)[0]
off = pe + 24 + opt
tva = tsz = 0
for i in range(nsec):
    nm = after[off:off + 8].rstrip(b'\0').decode('latin1')
    vsz, va, rsz, raw = struct.unpack_from('<IIII', after, off + 8)
    if nm == '.text':
        tva, tsz = va, max(vsz, rsz)
    off += 40

PAGE = 0x1000
newly = []
for rva in range(tva, tva + tsz, PAGE):
    b = before[rva:rva + PAGE]
    a = after[rva:rva + PAGE]
    if len(a) < PAGE:
        break
    if b.count(0) == len(b) and a.count(0) != len(a):
        newly.append(rva)
newset = set(newly)
print('newly decrypted pages: %d' % len(newly))
for p in newly:
    print('   0x%07X' % p)

# ---- live UFunction walk ----
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t()
    if not k.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o + 4], 'little')
def u64(b, o): return int.from_bytes(b[o:o + 8], 'little')
def ptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0


_nc = {}
def fname(i):
    if i in _nc: return _nc[i]
    blk, o = i >> 16, (i & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8); r = '?'
    if bp:
        bp = int.from_bytes(bp, 'little')
        if ptr(bp):
            hd = rpm(bp + o, 2)
            if hd:
                hd = int.from_bytes(hd, 'little'); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + o + 2, ln * (2 if wide else 1))
                    if s:
                        r = (''.join(chr(s[j*2] | (s[j*2+1] << 8)) for j in range(ln)) if wide
                             else s.decode('latin1', 'replace'))
    _nc[i] = r; return r


_cn = {}
def clsname(c):
    if c in _cn: return _cn[c]
    b = rpm(c + 0x20, 4); r = fname(u32(b, 0)) if b else '?'; _cn[c] = r; return r


hdr = rpm(OBJOBJECTS, 0x18)
objectsPtr, numEl = u64(hdr, 0), u32(hdr, 0x14)
chunks = rpm(objectsPtr, ((numEl + PERCHUNK - 1) // PERCHUNK) * 8)
hits, scanned = [], 0
for ci in range((numEl + PERCHUNK - 1) // PERCHUNK):
    ch = u64(chunks, ci * 8)
    if not ptr(ch): continue
    cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
    items = rpm(ch, cnt * STRIDE)
    if not items: continue
    for j in range(cnt):
        o = u64(items, j * STRIDE)
        if not ptr(o): continue
        cb = rpm(o + 0x18, 8)
        if not cb: continue
        c = int.from_bytes(cb, 'little')
        if not ptr(c): continue
        if clsname(c) != 'Function': continue
        scanned += 1
        fb = rpm(o + 0xE0, 8)
        if not fb: continue
        f = int.from_bytes(fb, 'little')
        if not ptr(f): continue
        rva = f - BASE
        if (rva & ~(PAGE - 1)) in newset:
            nb = rpm(o + 0x20, 4)
            hits.append((rva, fname(u32(nb, 0)) if nb else '?'))
print('\nlive UFunction objects scanned: %d' % scanned)
print('UFunctions whose native Func lands in a NEWLY DECRYPTED page: %d' % len(hits))
for rva, nm in sorted(set(hits)):
    print('   0x%07X  %s' % (rva, nm))
