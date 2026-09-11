import sys, struct, re
sys.path.insert(0,'scratchpad/s141/lanes/L2tools')
from l2pe import L2Img
img = L2Img('dumps/merged14.dump.exe')
buf = img.buf
base = img.imagebase

def find_all(needle, sect=None):
    out=[]; i=0
    while True:
        i = buf.find(needle, i)
        if i<0: break
        s = img.sect_of(i)
        if sect is None or (s and s['name']==sect): out.append(i)
        i+=1
    return out

names = [b'WorldToGravityTransform\x00', b'GravityToWorldTransform\x00',
         b'Velocity\x00', b'Acceleration\x00', b'MinAnalogWalkSpeed\x00']
strrva = {}
for n in names:
    hits = find_all(n)
    strrva[n.decode().strip('\x00')] = hits
    print("string %-26s hits: %s" % (n.decode().strip('\x00'), ['0x%08X(%s)'%(h, img.sect_of(h)['name'] if img.sect_of(h) else '?') for h in hits[:6]]))
print()
# find pointers to each string, then hexdump the record
def ptrs_to(rva):
    tgt = struct.pack('<Q', base + rva)
    res=[]; i=0
    while True:
        i = buf.find(tgt, i)
        if i<0: break
        res.append(i); i+=1
    return res

for nm in ['WorldToGravityTransform','GravityToWorldTransform','MinAnalogWalkSpeed','Velocity','Acceleration']:
    for h in strrva[nm][:3]:
        ps = ptrs_to(h)
        for p in ps:
            s = img.sect_of(p)
            print("=== %s  str@0x%08X  ptr-slot@0x%08X (%s) ===" % (nm, h, p, s['name'] if s else '?'))
            d = img.read(p, 0x40)
            for k in range(0,0x40,8):
                q = struct.unpack_from('<Q', d, k)[0]
                ann=''
                if base <= q < base+img.sizeofimage:
                    r = q-base
                    sec = img.sect_of(r)
                    ann = ' -> rva 0x%08X (%s)' % (r, sec['name'] if sec else '?')
                    if sec and sec['name']=='.rdata':
                        tx = img.read(r, 40).split(b'\x00')[0]
                        if 1<=len(tx)<=39 and all(32<=c<127 for c in tx): ann += ' "%s"' % tx.decode()
                lo,hi = struct.unpack_from('<II', d, k)
                w0,w1,w2,w3 = struct.unpack_from('<HHHH', d, k)
                print("   +0x%02X %016X  u32=(0x%08X,0x%08X) u16=(0x%X,0x%X,0x%X,0x%X)%s" % (k,q,lo,hi,w0,w1,w2,w3,ann))
            print()
