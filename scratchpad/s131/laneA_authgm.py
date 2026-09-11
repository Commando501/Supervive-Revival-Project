import sys, os, struct, collections, csv, bisect
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import fkdis, rectab
rectab.P['merged4']=os.path.join(os.getcwd(),'dumps','merged4.dump.exe')
img=fkdis.Img(os.path.join(os.getcwd(),'dumps','merged4.dump.exe')); IB=img.imagebase; b=img.buf
recs=rectab.scan('merged4')
byimpl=collections.defaultdict(list)
for r in recs: byimpl[r['impl']].append(r['name'])
pd=[]
with open(r"tools\strxref\index\pdata_union.csv",newline='') as f:
    rd=csv.reader(f); next(rd)
    for row in rd: pd.append((int(row[0],0),int(row[1],0)))
pd.sort(); starts=[x[0] for x in pd]
def rowof(r):
    i=bisect.bisect_right(starts,r)-1
    return pd[i] if i>=0 and pd[i][0]<=r<pd[i][1] else None
def chain_start(r):
    row=rowof(r)
    if not row: return None
    s=row[0]
    while True:
        i=bisect.bisect_right(starts,s-1)-1
        if i<0: break
        if pd[i][1]==s: s=pd[i][0]
        else: break
    return s
nm,vaddr,vsize,rawptr,rawsize=[s for s in img.sections if s[0]=='.text'][0]
blob=b[rawptr:rawptr+rawsize]
# mov r64,[rcx+0x250]  -> 48 8b XX 50 02 00 00 where XX in {0x81 rax,0x89 rcx,0x91 rdx,0x99 rbx,0xb1 rsi,0xb9 rdi}
regs={0x81:'rax',0x89:'rcx',0x91:'rdx',0x99:'rbx',0xa9:'rbp',0xb1:'rsi',0xb9:'rdi'}
hits=[]
i=0
n=len(blob)
while True:
    i=blob.find(b"\x50\x02\x00\x00", i)
    if i<0: break
    if i>=3 and blob[i-3]==0x48 and blob[i-2]==0x8b and blob[i-1] in regs:
        hits.append((vaddr+i-3, regs[blob[i-1]]))
    i+=1
print(f"`mov r64,[rcx+0x250]` occurrences in .text (unit: instructions) = {len(hits)}")
print("  (0x250 established as UWorld::AuthorityGameMode from UGameplayStatics::GetGameMode impl 0x37D7BF0)")
for r,reg in hits:
    cs=chain_start(r)
    off = r-cs if cs else None
    tag=f"fnstart=0x{cs:07X} (+0x{off:X})" if cs else "no-pdata"
    names = byimpl.get(cs,[]) if cs else []
    print(f"   0x{r:07X}  mov {reg},[rcx+0x250]   {tag} names={names}")
