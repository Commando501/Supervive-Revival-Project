import sys, struct, re
sys.path.insert(0,'scratchpad/s139')
from img import DATA, IMAGEBASE, SECS, sec_of, q, d

def find_ascii(name, sect=None):
    """exact ascii string, NUL-terminated, preceded by NUL"""
    pat = b'\x00'+name.encode()+b'\x00'
    out=[]
    i=0
    while True:
        i = DATA.find(pat, i)
        if i<0: break
        out.append(i+1)
        i+=1
    return [r for r in out if sect is None or sec_of(r)==sect]

def find_ptrs(rva, align=8):
    """qwords in image equal to IMAGEBASE+rva"""
    target = struct.pack('<Q', IMAGEBASE+rva)
    out=[]; i=0
    while True:
        i = DATA.find(target, i)
        if i<0: break
        if i%align==0: out.append(i)
        i+=1
    return out

def is_text(v):
    return IMAGEBASE+0x1000 <= v < IMAGEBASE+0x764A000

if __name__=="__main__":
    name=sys.argv[1]
    for s in find_ascii(name):
        print("string rva 0x%08X sec=%s"%(s, sec_of(s)))
        for p in find_ptrs(s):
            print("   ptr at 0x%08X (%s):"%(p, sec_of(p)), end=' ')
            vals=[q(p+8*k) for k in range(1,4)]
            print(' '.join(("0x%X%s"%(v-IMAGEBASE, "[T]" if is_text(v) else "")) if v>IMAGEBASE and v<IMAGEBASE+0x0B000000 else "0x%X"%v for v in vals))
