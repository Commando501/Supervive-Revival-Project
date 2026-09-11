import struct, sys, os
PATH = os.environ.get("IMG", r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe")
DATA = open(PATH,'rb').read()
pe = struct.unpack_from('<I', DATA, 0x3c)[0]
assert DATA[pe:pe+4]==b'PE\0\0'
nsec = struct.unpack_from('<H', DATA, pe+6)[0]
optsz = struct.unpack_from('<H', DATA, pe+20)[0]
IMAGEBASE = struct.unpack_from('<Q', DATA, pe+24+24)[0]
secoff = pe+24+optsz
SECS=[]
for i in range(nsec):
    o=secoff+i*40
    name=DATA[o:o+8].rstrip(b'\0').decode('latin1')
    vsz,va,rsz,rptr = struct.unpack_from('<IIII', DATA, o+8)
    SECS.append((name,va,vsz,rptr,rsz))
def sec_of(rva):
    for n,va,vs,rp,rs in SECS:
        if va<=rva<va+max(vs,rs): return n
    return None
def rd(rva,n):
    return DATA[rva:rva+n]
def q(rva): return struct.unpack_from('<Q',DATA,rva)[0]
def d(rva): return struct.unpack_from('<I',DATA,rva)[0]
if __name__=="__main__":
    print("ImageBase 0x%X"%IMAGEBASE)
    for s in SECS: print("%-10s va=0x%08X vsz=0x%08X rptr=0x%08X rsz=0x%08X"%(s[0],s[1],s[2],s[3],s[4]))
