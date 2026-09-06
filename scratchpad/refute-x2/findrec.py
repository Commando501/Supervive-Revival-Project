import sys,struct; sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
path=sys.argv[1]; target=int(sys.argv[2],16)
p=PE(path); d=p.data; ib=p.imagebase
va=ib+target
needle=struct.pack('<Q',va)
occ=[]
i=0
while True:
    j=d.find(needle,i)
    if j<0: break
    occ.append(j); i=j+1
print('occurrences of VA 0x%X: %d'%(va,len(occ)))
def secof(rva):
    for s in p.secs:
        if s['vaddr']<=rva<s['vaddr']+s['vsize']: return s['name']
    return '?'
def readcstr(rva,n=64):
    b=d[rva:rva+n]
    z=b.find(b'\0')
    return b[:z if z>=0 else n]
for j in occ[:12]:
    print(' at 0x%08X (%s)'%(j,secof(j)))
    for k in range(-4,5):
        o=j+k*8
        if o<0 or o+8>len(d): continue
        q=struct.unpack_from('<Q',d,o)[0]
        tag=''
        if ib<=q<ib+len(d):
            r=q-ib
            tag=' -> rva 0x%X (%s)'%(r,secof(r))
            s=readcstr(r,48)
            if s and all(32<=c<127 for c in s) and len(s)>3: tag+='  cstr=%r'%s
        print('   [%+d] 0x%016X%s'%(k,q,tag))
