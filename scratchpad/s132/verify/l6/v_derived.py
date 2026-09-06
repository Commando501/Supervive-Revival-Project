import struct,json,bisect,re
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
F=json.load(open(r'scratchpad/s132/verify/l6/myfuncs.json'))
hits=json.load(open(r'scratchpad/s132/verify/l6/myneg.json'))
BEG=[f[0] for f in F]
def func_of(r):
    i=bisect.bisect_right(BEG,r)-1
    if i<0: return None
    b,e,u=F[i]
    return (b,e) if b<=r<e else None
def r2f(r):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=r<va+max(vs,rs): return ra+(r-va),nm
    return None,None
# computed-tail set
tails=set()
for b,e,u in F:
    o,nm=r2f(e-3)
    t3=D[o:o+3]
    if (t3[0]==0x41 and t3[1]==0xFF and 0xE0<=t3[2]<=0xE7) or (t3[1]==0xFF and 0xE0<=t3[2]<=0xE7):
        tails.add(b)
print("computed-tail functions:",len(tails))
# 4.3 derived
inside_tail=0; per_fn={}
for nm,site,imm,tgt in hits:
    fn=func_of(site)
    if fn and fn[0] in tails:
        inside_tail+=1; per_fn.setdefault(fn[0],0); per_fn[fn[0]]+=1
print("of the %d constants, sit inside a computed-tail function: %d (%.0f%%)"%(len(hits),inside_tail,100*inside_tail/len(hits)))
p31tails=[b for b in tails if 0x1520000<=b<0x1520000+0x2a48628]
print("packer31 computed-tail functions:",len(p31tails))
print("of those, carry >=1 such constant: %d (%.1f%%)"%(len(per_fn),100*len(per_fn)/len(p31tails)))
# 3.6 corroborating: same-register +1 in last 80 bytes of a computed-tail function
REGS=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+['r%d'%i for i in range(8,16)]
def plus1(b):
    n=len(b); out=[]
    for i in range(n-4):
        c0=b[i]
        if c0 in (0x48,0x49):
            hi=8 if c0==0x49 else 0; c1=b[i+1]
            if c1==0xFF and 0xC0<=b[i+2]<=0xC7: out.append((i,hi+(b[i+2]-0xC0)))
            elif c1==0x83 and 0xC0<=b[i+2]<=0xC7 and b[i+3]==0x01: out.append((i,hi+(b[i+2]-0xC0)))
            elif c1==0x83 and 0xE8<=b[i+2]<=0xEF and b[i+3]==0xFF: out.append((i,hi+(b[i+2]-0xE8)))
            elif c1==0x81 and 0xC0<=b[i+2]<=0xC7 and b[i+3:i+7]==b'\x01\x00\x00\x00': out.append((i,hi+(b[i+2]-0xC0)))
        if c0 in (0x48,0x49,0x4C,0x4D) and b[i+1]==0x8D:
            mrm=b[i+2]
            if 0x40<=mrm<=0x7F and (mrm&7)!=4 and b[i+3]==0x01:
                out.append((i,((mrm>>3)&7)+(8 if c0 in (0x4C,0x4D) else 0)))
    return out
cnt=0
for b in tails:
    e=next(x[1] for x in F if x[0]==b) if False else None
for bb,ee,uu in F:
    if bb not in tails: continue
    o,nm=r2f(ee-3); t3=D[o:o+3]
    if t3[0]==0x41 and t3[1]==0xFF: reg=8+(t3[2]-0xE0)
    else:
        # account REX.B prefix (0x49/0x4D) that report ignored
        o2,_=r2f(ee-3)
        pre=D[o2]
        reg=(t3[2]-0xE0)+(8 if pre in (0x41,0x49,0x4D,0x45) else 0)
    start=max(bb,ee-80)
    oo,_=r2f(start)
    blk=D[oo:oo+(ee-start)]
    if any(r==reg for _,r in plus1(blk)): cnt+=1
print("computed-tail fns with same-register +1 in last 80 bytes: %d / %d (%.1f%%)"%(cnt,len(tails),100*cnt/len(tails)))
# distance histogram of the 406
