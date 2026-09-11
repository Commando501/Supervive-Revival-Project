import sys,struct
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
TEXT_VA=4096; TEXT_SZ=124030976
lo=int(sys.argv[1],16); hi=int(sys.argv[2],16)
end=TEXT_VA+TEXT_SZ
i=TEXT_VA; res={}
while i<end-5:
    b=d[i]
    if b==0xE8 or b==0xE9:
        rel=struct.unpack_from('<i',d,i+1)[0]
        t=i+5+rel
        if lo<=t<hi:
            res.setdefault(t,[]).append((i,'call' if b==0xE8 else 'jmp'))
    i+=1
for t in sorted(res):
    print("target 0x%08x : %d"%(t,len(res[t])))
    for s,k in res[t][:40]: print("   0x%08x %s"%(s,k))
