import sys, os, struct, collections
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import fkdis, rectab
rectab.P['merged4']=os.path.join(os.getcwd(),'dumps','merged4.dump.exe')
img=fkdis.Img(os.path.join(os.getcwd(),'dumps','merged4.dump.exe')); IB=img.imagebase; b=img.buf
recs=rectab.scan('merged4')
byimpl=collections.defaultdict(list)
for r in recs: byimpl[r['impl']].append(r['name'])
nm,vaddr,vsize,rawptr,rawsize=[s for s in img.sections if s[0]=='.text'][0]
blob=b[rawptr:rawptr+rawsize]
GW=0x35AFC40
sites=[]
for i in range(len(blob)-5):
    if blob[i]==0xE8:
        d=struct.unpack_from("<i",blob,i+1)[0]
        if vaddr+i+5+d==GW: sites.append(vaddr+i)
print(f"direct E8 call sites to the uncached world getter 0x{GW:07X} (unit: call sites) = {len(sites)}")
succ=collections.Counter()
for s in sites:
    # expect: 48 8b c8 (mov rcx,rax) then E8 rel32
    p=s+5
    if b[p:p+3]==b"\x48\x8b\xc8" and b[p+3]==0xE8:
        d=struct.unpack_from("<i",b,p+4)[0]
        t=p+3+5+d
        succ[t]+=1
print(f"of which immediately followed by `mov rcx,rax; call Y` (unit: call sites) = {sum(succ.values())}")
print("Y histogram:")
for t,c in succ.most_common(40):
    tag = rectab.FOLD.get(t,'')
    nmz = byimpl.get(t,[])
    first = b[t:t+12].hex()
    print(f"   0x{t:07X}  x{c:<3}  {tag:<22} names={nmz}  bytes={first}")
