import sys,struct
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
exec(open(r"G:\git\Supervive Revival Project\scratchpad\s139\adv\uht2.py").read().split("if __name__")[0])
key=sys.argv[1]; must=sys.argv[2]
pat=(key+'\0').encode(); i=RLO; cands=[]
while True:
    i=DATA.find(pat,i,RHI)
    if i<0: break
    if DATA[i-1]==0: cands.append(i)
    i+=1
recs=[]
for c in cands:
    for r in ptrs_to(c):
        if rec_ok(r)==key: recs.append(r)
done=set()
for r in recs:
    for a in ptrs_to(r):
        lo=a
        while lo-8>=RLO:
            v=u64(lo-8)-IMAGEBASE
            if not (RLO<=v<RHI) or rec_ok(v) is None: break
            lo-=8
        hi=a
        while hi+8<RHI:
            v=u64(hi+8)-IMAGEBASE
            if not (RLO<=v<RHI) or rec_ok(v) is None: break
            hi+=8
        if lo in done: continue
        n=(hi-lo)//8+1
        names=[rec_ok(u64(lo+k*8)-IMAGEBASE) for k in range(n)]
        if must in names:
            done.add(lo)
            print(f"### array 0x{lo:08X} n={n}")
            for k in range(n):
                rr=u64(lo+k*8)-IMAGEBASE
                gf=u32(rr+0x18)
                isbool = (gf & 0xFF)==0x0C
                print(f"   {'BOOL ' if isbool else '+0x%04X'%u16(rr+0x32)}  {rec_ok(rr)}")
