import struct,json,re
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
IB=0x200000000; SOI=0x4066000
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
base,size=0x127A000,0x10AC
fo,_=r2f(base)
p=0; types={}; secs={}; targets=[]
while p<size:
    pg,blk=struct.unpack_from('<II',D,fo+p)
    if blk==0: break
    n=(blk-8)//2
    for i in range(n):
        e=struct.unpack_from('<H',D,fo+p+8+2*i)[0]
        t=e>>12; off=e&0xFFF
        types[t]=types.get(t,0)+1
        rva=pg+off
        _,nm=r2f(rva); secs[nm]=secs.get(nm,0)+1
        if t==10: targets.append(rva)
    p+=blk
print("bytes consumed %d of %d"%(p,size))
print("type histogram (10=DIR64,0=ABSOLUTE):",types)
print("reloc site sections:",secs)
inrange=0; low=[]
for rva in targets:
    o,_=r2f(rva)
    v=struct.unpack_from('<Q',D,o)[0]
    if IB<=v<IB+0x1000: low.append((hex(rva),hex(v)))
    if IB<=v<IB+SOI: inrange+=1
print("DIR64 count:",len(targets)," values inside image:",inrange)
print("DIR64 values in [IB, IB+0x1000):",len(low),low[:10])
# any DIR64 value == IB+1 exactly?
eq=[(hex(r)) for r in targets if struct.unpack_from('<Q',D,r2f(r)[0])[0]==IB+1]
print("DIR64 value == ImageBase+1:",eq)
# 3.2
print("\n--- 3.2 ---")
pat=struct.pack('<Q',0x200000001)
occ=[m.start() for m in re.finditer(re.escape(pat),D)]
print("literal qword 0x200000001 file-wide occurrences:",len(occ))
al=[]
for o in occ:
    rv,nm=None,None
    for s in SEC:
        if s[3]<=o<s[3]+s[4]: rv=s[1]+(o-s[3]); nm=s[0]
    al.append((hex(o),nm,hex(rv) if rv is not None else None, (rv%8==0) if rv is not None else None))
for a in al: print("   ",a)
o,_=r2f(0x941900); print("bytes at RVA 941900:",D[o:o+16].hex())
o2,_=r2f(0x941908); v=struct.unpack_from('<Q',D,o2)[0]
print("qword at 941908 = %016x  (IB+0x7000 = %016x)"%(v,IB+0x7000))
print("is 941908 a DIR64 reloc target?", 0x941908 in targets)
print("is 941900 a DIR64 reloc target?", 0x941900 in targets)
