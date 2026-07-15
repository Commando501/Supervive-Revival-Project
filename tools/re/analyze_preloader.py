import struct, sys, math, re
p = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\preloader.dll"
d = open(p,'rb').read()
print("file size:", len(d))
# PE headers
e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
assert d[e_lfanew:e_lfanew+4] == b'PE\x00\x00'
coff = e_lfanew+4
nsec = struct.unpack_from('<H', d, coff+2)[0]
optsz = struct.unpack_from('<H', d, coff+16)[0]
opt = coff+20
magic = struct.unpack_from('<H', d, opt)[0]
imagebase = struct.unpack_from('<Q', d, opt+24)[0]
entry = struct.unpack_from('<I', d, opt+16)[0]
print("PE32+  imagebase=0x%X  entry-rva=0x%X  nsec=%d" % (imagebase, entry, nsec))
# data directories: import @ index1, at opt+112 (PE32+)
dd = opt+112
imp_rva, imp_sz = struct.unpack_from('<II', d, dd + 1*8)
print("import dir rva=0x%X size=0x%X" % (imp_rva, imp_sz))
sects = []
sh = opt+optsz
def entropy(b):
    if not b: return 0
    freq=[0]*256
    for x in b: freq[x]+=1
    e=0
    for f in freq:
        if f: pr=f/len(b); e-=pr*math.log2(pr)
    return e
print("\n--- sections ---")
for i in range(nsec):
    o=sh+i*40
    nm=d[o:o+8].rstrip(b'\x00').decode('latin1')
    vsz,vaddr,rsz,raddr = struct.unpack_from('<IIII', d, o+8)
    chars = struct.unpack_from('<I', d, o+36)[0]
    body = d[raddr:raddr+rsz]
    sects.append((nm,vaddr,vsz,raddr,rsz))
    print("  %-8s vaddr=0x%-6X vsz=0x%-6X raw=0x%-6X rsz=0x%-6X entropy=%.2f exec=%s" %
          (nm, vaddr, vsz, raddr, rsz, entropy(body), bool(chars & 0x20000000)))
def rva2off(rva):
    for nm,va,vsz,ra,rsz in sects:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
    return None
# imports
print("\n--- imports ---")
try:
    off = rva2off(imp_rva); idx=0
    while True:
        oft,tstamp,fwd,namerva,firstthunk = struct.unpack_from('<IIIII', d, off+idx*20)
        if namerva==0 and oft==0: break
        dllname = d[rva2off(namerva):].split(b'\x00')[0].decode('latin1')
        # walk INT
        thunk_rva = oft or firstthunk; funcs=[]
        toff = rva2off(thunk_rva); j=0
        while True:
            v = struct.unpack_from('<Q', d, toff+j*8)[0]
            if v==0: break
            if v & 0x8000000000000000: funcs.append("ord#%d"%(v&0xFFFF))
            else:
                nrva=v & 0x7FFFFFFF; nm=d[rva2off(nrva)+2:].split(b'\x00')[0].decode('latin1'); funcs.append(nm)
            j+=1
        print("  %s: %s" % (dllname, ", ".join(funcs)))
        idx+=1
except Exception as ex:
    print("  (import parse error: %s)" % ex)
# constant search
print("\n--- constant search (crash artifacts) ---")
for label,val,width in [("R11=0x95654773B3BC",0x95654773B3BC,8),("Rbp=0x537AC9E1",0x537AC9E1,4),
                        ("R11 6-byte",0x95654773B3BC,6),("poison 0x7FF90E000001 6b",0x7FF90E000001,6)]:
    pat = val.to_bytes(width,'little')
    hits=[m.start() for m in re.finditer(re.escape(pat), d)]
    print("  %-26s pattern=%s hits=%s" % (label, pat.hex(), [hex(h) for h in hits[:8]]))
# strings
print("\n--- ASCII strings (len>=5) ---")
strs = re.findall(rb'[\x20-\x7e]{5,}', d)
seen=set()
for s in strs:
    t=s.decode('latin1')
    if t not in seen:
        seen.add(t)
        if any(k in t.lower() for k in ('nt','thread','protect','virtual','hook','tamper','integrity','check','loki','preload','debug','memory','module','ldr','peb','crc','hash','sig')):
            print("  ", t)
