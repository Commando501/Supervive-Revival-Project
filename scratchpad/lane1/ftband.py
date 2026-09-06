import pickle, collections
ft=pickle.load(open('scratchpad/lane1/ft.pkl','rb')); BEG,END,PHB=ft['BEG'],ft['END'],ft['PHB']
N=len(BEG)
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000; TEND=TEXT+NP*0x1000
nd=collections.Counter(); rd=collections.Counter()
# approximate extent for never-decrypted slots: distance to next slot's begin
allb=[]
for i in range(N):
    b = BEG[i] if END[i] else PHB[i]
    allb.append(b)
ndbytes=collections.Counter()
for i in range(N):
    b=allb[i]
    if not (TEXT<=b<TEND): continue
    band=b//0x100000
    if END[i]: rd[band]+=1
    else:
        nd[band]+=1
        nxt=allb[i+1] if i+1<N else b
        sz=max(0,min(nxt-b, 65536))
        ndbytes[band]+=sz
print(f"{'band':>11} {'darkpg':>7} {'decrypted fns':>14} {'NEVER-decrypted fns':>20} {'ndKB':>8}")
tot_nd=0
for band in range(0,(TEND//0x100000)+1):
    p0=(band*0x100000)//0x1000; p1=min(NP,((band+1)*0x100000)//0x1000)
    if p0>=NP: break
    dk=sum(1 for p in range(max(p0,0),p1) if bm[p]==0)
    if nd[band]==0 and rd[band]==0: continue
    tot_nd+=nd[band]
    print(f"0x{band*0x100000:07X} {dk:7d} {rd[band]:14d} {nd[band]:20d} {ndbytes[band]//1024:8d}")
print("total never-decrypted fns in .text:",tot_nd)
lowsum=sum(nd[b] for b in range(0,0xC)); lowb=sum(ndbytes[b] for b in range(0,0xC))
print(f"RVA < 0x0C00000 : never-decrypted fns {lowsum} ({100.0*lowsum/tot_nd:.1f}% of all) approx {lowb//1024} KB")
