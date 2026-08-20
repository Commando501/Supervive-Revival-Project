import sys, struct, collections, os, csv, bisect
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import fkdis, rectab
rectab.P['merged4']=os.path.join(os.getcwd(),'dumps','merged4.dump.exe')
img=fkdis.Img(os.path.join(os.getcwd(),'dumps','merged4.dump.exe')); IB=img.imagebase; b=img.buf
recs=rectab.scan('merged4'); byimpl=collections.defaultdict(list)
for r in recs: byimpl[r['impl']].append(r['name'])
pd=[]
with open(r"tools\strxref\index\pdata_union.csv",newline='') as f:
    rd=csv.reader(f); next(rd)
    for row in rd: pd.append((int(row[0],0),int(row[1],0)))
pd.sort(); starts=[x[0] for x in pd]
def chain_start(r):
    i=bisect.bisect_right(starts,r)-1
    if i<0 or not (pd[i][0]<=r<pd[i][1]): return None
    s=pd[i][0]
    while True:
        j=bisect.bisect_right(starts,s-1)-1
        if j<0 or pd[j][1]!=s: break
        s=pd[j][0]
    return s
nm,va,vs,rp,rs=[s for s in img.sections if s[0]=='.text'][0]
blob=b[rp:rp+rs]
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
md=Cs(CS_ARCH_X86,CS_MODE_64)
def callers(t):
    out=[]
    for i in range(len(blob)-5):
        if blob[i] in (0xE8,0xE9):
            d=struct.unpack_from("<i",blob,i+1)[0]
            if va+i+5+d==t: out.append((va+i, 'call' if blob[i]==0xE8 else 'jmp'))
    return out
for t,lbl in [(0x5630970,'GetLokiGameMode impl (gutted)'),
              (0x55C7DD0,'IsA<ALokiRoundGameMode> helper'),
              (0x5453580,'ALokiRoundGameMode::StaticClass'),
              (0x37D7BF0,'UGameplayStatics::GetGameMode impl')]:
    cs=callers(t)
    print(f"\n=== callers of 0x{t:07X} ({lbl}) — UNCAPPED, unit: call/jmp sites = {len(cs)}")
    for site,kind in cs[:40]:
        st=chain_start(site)
        n=byimpl.get(st,[]) if st else []
        # what feeds rcx: previous 2 instructions
        pre=[]
        for s0 in range(site-24, site):
            tmp=[x for x in md.disasm(b[s0:site], IB+s0)]
            if tmp and tmp[-1].address-IB+tmp[-1].size==site and len(tmp)>=2:
                pre=tmp[-2:]; break
        ps=" | ".join(f"{x.mnemonic} {x.op_str}" for x in pre)
        sts=f"0x{st:07X}" if st else "no-pdata"
        print(f"   {kind} @0x{site:07X}  in fn {sts} {n}   PRE: {ps}")
